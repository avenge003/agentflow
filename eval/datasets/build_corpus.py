#!/usr/bin/env python3
"""评测语料构建脚本（按 test_datasets.md §2 规范）

流程：
  1. 扫描 docs/GMP/{SOP,SMP}/
  2. 按比例采样代表性 docx：SOP 60% / SMP 25% / 附录 10% / 边缘 5%
  3. 抽取段落 + 表格 → 拼成单一文本
  4. 按规则分块：chunk_size=400, chunk_overlap=80
     splitter 策略：句末标号 + 段落标题双锚点
  5. 写入 eval/datasets/eval_corpus.jsonl

每个 chunk 格式（test_datasets.md §2.3）：
  {
    "chunk_id": "<doc_id>::p<n>::c<i>",
    "doc_id":   "<doc_id>",
    "title":    "<doc 标题>",
    "subject":  "<推断的 subject>",
    "content":  "<chunk 文本>",
    "metadata": {
      "doc_no": ..., "rev": ..., "effective_date": ...,
      "dept": ..., "category": ...
    }
  }

注意：脚本本身**入 git**（可复跑），生成的 eval_corpus.jsonl **可入 git**
（脱敏等价集，规模可控）。
"""

import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from docx import Document


# ==================== 采样 ====================


SOP_DIR = Path("docs/GMP/SOP")
SMP_DIR = Path("docs/GMP/SMP")
OUT_PATH = Path("eval/datasets/eval_corpus.jsonl")

# 目标 chunk 数（spec §2.4）
TARGET_TOTALS = {"SOP": 300, "SMP": 125, "appendix": 50, "edge": 25}

# 采样配额：SOP 18 + SMP 8 + 附录 2 + 边缘 1 = 29（spec 允许 10–15，
# 这里 29 个以保证总 chunk ≥ 500；每个目标 docx 平均 ≥ 20 chunk 即可）
SAMPLE_COUNTS = {"SOP": 18, "SMP": 8, "appendix": 2, "edge": 1}


@dataclass
class Doc:
    path: Path
    doc_id: str
    title: str
    category: str  # SOP / SMP / appendix / edge


def list_docx(d: Path) -> List[Path]:
    return sorted(p for p in d.iterdir() if p.suffix.lower() == ".docx")


def infer_category(name: str) -> str:
    """从文件名粗判 category"""
    base = name.lower()
    if "权限" in name or "详单" in name or "分配" in name:
        return "edge"  # 权限详单类边缘
    if "附件" in name or "附录" in name or "附表" in name:
        return "appendix"
    if "记录" in name or "凭证" in name or "申请表" in name:
        return "edge"  # 记录类当作边缘样本
    if "sop" in base or "sop" in name[:5].lower():
        return "SOP"
    if "smp" in base or "smp" in name[:5].lower():
        return "SMP"
    return "edge"


def doc_id_from_filename(name: str) -> str:
    """提取 doc_id：'SOPQC-FL015-3-01 交联聚维酮...' → 'SOPQC-FL015-3-01'

    规则：取第一个空白前的 token；若以 (修订号XX) 结尾则去掉
    """
    name = name.rsplit(".", 1)[0]  # 去后缀
    # 去 (修订号XX) / （修订号XX）
    name = re.sub(r"[\(\（]修订号\s*\d+[\)\）]", "", name)
    # 去 [附件X] / （附件X）
    name = re.sub(r"[\(\（][附件]\s*\w+[\)\）]", "", name)
    parts = name.split(maxsplit=1)
    return parts[0] if parts else name


def title_from_filename(name: str) -> str:
    name = name.rsplit(".", 1)[0]
    name = re.sub(r"[\(\（]修订号\s*\d+[\)\）]", "", name)
    name = re.sub(r"[\(\（][附件]\s*\w+[\)\）]", "", name)
    parts = name.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else parts[0]


def sample_docs(seed: int = 42) -> List[Doc]:
    rng = random.Random(seed)
    sop_all = [p for p in list_docx(SOP_DIR) if infer_category(p.name) == "SOP"]
    smp_all = [p for p in list_docx(SMP_DIR) if infer_category(p.name) == "SMP"]
    apx_all = (
        [p for p in list_docx(SOP_DIR) + list_docx(SMP_DIR) if infer_category(p.name) == "appendix"]
    )
    edge_all = (
        [p for p in list_docx(SOP_DIR) + list_docx(SMP_DIR) if infer_category(p.name) == "edge"]
    )

    print(f"[scan] SOP={len(sop_all)}, SMP={len(smp_all)}, 附录={len(apx_all)}, 边缘={len(edge_all)}")

    sampled: List[Doc] = []
    for n in (SAMPLE_COUNTS["SOP"],):
        for p in rng.sample(sop_all, n):
            sampled.append(Doc(p, doc_id_from_filename(p.name), title_from_filename(p.name), "SOP"))
    for p in rng.sample(smp_all, SAMPLE_COUNTS["SMP"]):
        sampled.append(Doc(p, doc_id_from_filename(p.name), title_from_filename(p.name), "SMP"))
    for p in rng.sample(apx_all, SAMPLE_COUNTS["appendix"]):
        sampled.append(
            Doc(p, doc_id_from_filename(p.name), title_from_filename(p.name), "appendix")
        )
    for p in rng.sample(edge_all, SAMPLE_COUNTS["edge"]):
        sampled.append(Doc(p, doc_id_from_filename(p.name), title_from_filename(p.name), "edge"))

    return sampled


# ==================== 文本抽取 ====================


def docx_to_blocks(path: Path) -> List[Tuple[str, str]]:
    """(kind, text) 列表。kind ∈ {p, t} 段/表"""
    doc = Document(str(path))
    blocks: List[Tuple[str, str]] = []
    # 按文档顺序遍历 body：paragraphs 与 tables 混排
    body = doc.element.body
    p_iter = iter(doc.paragraphs)
    t_iter = iter(doc.tables)
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            try:
                p = next(p_iter)
            except StopIteration:
                continue
            t = p.text.strip()
            if t:
                blocks.append(("p", t))
        elif tag == "tbl":
            try:
                tbl = next(t_iter)
            except StopIteration:
                continue
            rows = []
            for row in tbl.rows:
                cells = [c.text.strip() for c in row.cells]
                rows.append(" | ".join(cells))
            t = "\n".join(rows).strip()
            if t:
                blocks.append(("t", t))
    return blocks


# ==================== 分块 ====================


CHUNK_SIZE = 400
CHUNK_OVERLAP = 80

# 段落标题锚点：形如 "1." / "1.1" / "一、" / "目的：" / "范围："
HEADING_PAT = re.compile(
    r"^(?:"
    r"\d+(?:\.\d+){0,3}\s*[.、\)）]?"  # 1. / 1.1 / 1) / 1、
    r"|[一二三四五六七八九十]+[、.]"  # 一、
    r"|目的|范围|职责|规程|定义|术语|缩写|参考|附录|记录|附则"
    r")"
)
SENT_END = set("。！？!?；;…")


def split_anchors(text: str) -> List[Tuple[int, int]]:
    """找出所有可作为分块锚点的位置（句子/段落边界）"""
    anchors: List[Tuple[int, int]] = [(0, 0)]
    pos = 0
    for m in HEADING_PAT.finditer(text):
        if m.start() > 0:
            anchors.append((m.start(), m.start() - pos))
    # 加句末
    for i, ch in enumerate(text):
        if ch in SENT_END:
            anchors.append((i + 1, i + 1 - pos))
    return anchors


def chunk_text(text: str) -> List[str]:
    """按 chunk_size 切，相邻 chunk 共享 chunk_overlap 字符"""
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + CHUNK_SIZE, n)
        # 尝试在 end 附近往前找最近一个锚点
        anchor = end
        window = text[start:end]
        for sep in ("。", "；", "！", "？", "\n", "|", "  "):
            idx = window.rfind(sep)
            if idx > CHUNK_SIZE // 2:
                anchor = start + idx + 1
                break
        else:
            anchor = end
        chunk = text[start:anchor].strip()
        if chunk:
            chunks.append(chunk)
        if anchor >= n:
            break
        start = max(anchor - CHUNK_OVERLAP, start + 1)
    return chunks


# ==================== subject 推断 ====================


def infer_subject(doc_id: str, title: str, content: str) -> str:
    """从 doc_id 前缀（QC/QA/CF/SC/WL/JS/VT/WJ/WL/GW/QC-FL/...）推断 subject"""
    head = doc_id[:3].upper()
    m = {
        "SOP": "QC",  # 默认 SOP 是 QC
        "SMP": "QA",
    }
    # 取 doc_id 的中段（QC / QA / CF / SC / WL / JS / VT / WJ / GW / YL / FL / CP / SB / TZ / WS / WX）
    m2 = {
        "QC": "QC/检验",
        "QA": "QA/质量保证",
        "CF": "CF/厂房设施",
        "SC": "SC/生产",
        "WL": "WL/物料",
        "JS": "JS/技术",
        "VT": "VT/验证",
        "WJ": "WJ/文件",
        "GW": "GW/管理",
        "YL": "QC/原料检验",
        "FL": "QC/辅料检验",
        "CP": "QC/成品检验",
        "SB": "SC/生产设备",
        "TZ": "QC/通用方法",
        "WS": "QA/卫生",
        "WX": "QA/维修",
    }
    if "-" in doc_id:
        seg = doc_id.split("-")[0]  # SOPQC
        # 取尾部两字母
        if len(seg) >= 5:
            tag = seg[-2:]
            if tag in m2:
                return m2[tag]
        # 退到 3 字母
        if len(seg) >= 4:
            tag = seg[-3:]
            if tag in m2:
                return m2[tag]
    return m.get(doc_id[:3].upper(), "未分类")


# ==================== 写入 ====================


def build_chunk(d: Doc, idx: int, content: str) -> dict:
    return {
        "chunk_id": f"{d.doc_id}::p{idx}::c0",
        "doc_id": d.doc_id,
        "title": d.title,
        "subject": infer_subject(d.doc_id, d.title, content),
        "content": content,
        "metadata": {
            "doc_no": d.doc_id,
            "rev": d.doc_id.split("-")[-1] if "-" in d.doc_id else "0",
            "dept": infer_subject(d.doc_id, d.title, content).split("/")[0],
            "category": d.category,
        },
    }


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    docs = sample_docs()
    print(f"[sample] 采到 {len(docs)} 个 docx")
    for d in docs:
        print(f"  - {d.category:9s} {d.doc_id}  {d.title[:40]}")
    print()

    all_chunks: List[dict] = []
    cat_counter: dict = {c: 0 for c in TARGET_TOTALS}
    for d in docs:
        blocks = docx_to_blocks(d.path)
        full_text = "\n".join(t for _, t in blocks)
        if not full_text:
            print(f"  ⚠ {d.doc_id} 抽取为空，跳过")
            continue
        chunks = chunk_text(full_text)
        for i, c in enumerate(chunks):
            all_chunks.append(build_chunk(d, i, c))
        cat_counter[d.category] = cat_counter.get(d.category, 0) + len(chunks)
        print(
            f"  ✓ {d.doc_id} ({d.category}): "
            f"text={len(full_text)}字, chunks={len(chunks)}"
        )

    # 不足配额时插边缘样本
    print()
    print(f"[chunks] 各类总计: {cat_counter}")
    for cat, target in TARGET_TOTALS.items():
        if cat_counter.get(cat, 0) < target:
            print(
                f"  ⚠ {cat} 不足：{cat_counter.get(cat, 0)} / {target}（差 {target - cat_counter.get(cat, 0)}）"
            )

    # 写文件
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"\n[write] {OUT_PATH}  共 {len(all_chunks)} chunks")

    return 0


if __name__ == "__main__":
    sys.exit(main())
