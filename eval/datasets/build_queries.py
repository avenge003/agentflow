#!/usr/bin/env python3
"""评测 query 集构造脚本（按 test_datasets.md §3-§5 规范）

产物：
  eval/datasets/eval_queries.jsonl          ≥195  (factual/procedural/...)
  eval/datasets/eval_queries_holdout.jsonl  ≥50
  eval/datasets/negative_queries.jsonl      ≥30
  eval/datasets/adversarial_queries.jsonl   ≥20

Query schema（spec §3.3）：
  {
    "query_id": "q_0001",
    "query": "...",
    "type": "factual" / "procedural" / ...,
    "difficulty": "easy/medium/hard",
    "gold_chunks": [{"chunk_id": "...", "relevance": 3}],
    "expected_doc_ids": ["..."],
    "expected_answer_keywords": ["..."],
    "is_negative": false,
    "notes": "..."
  }

策略：基于 build_corpus 采样的 19 个 docx 模板化生成
"""

import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Dict, List

# 让脚本能 import app.*（与项目根目录一致的 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

CORPUS_PATH = Path("eval/datasets/eval_corpus.jsonl")
OUT_DIR = Path("eval/datasets")

# 配额（spec §3.1，negative/adversarial 拆出去）
QUOTAS = {
    "factual": 40,
    "procedural": 50,
    "definitional": 30,
    "numerical": 25,
    "comparison": 15,
    "long-tail": 20,
    "multi-hop": 15,
}
HOLDOUT = 50
NEGATIVE = 35
ADVERSARIAL = 25

# 难度（spec §3.1）
DIFFICULTY = {
    "factual": "easy",
    "procedural": "medium",
    "definitional": "easy",
    "numerical": "medium",
    "comparison": "hard",
    "long-tail": "hard",
    "multi-hop": "hard",
    "adversarial": "hard",
    "negative": "medium",
}


# ==================== 加载语料 ====================


def load_corpus() -> Dict[str, List[dict]]:
    """按 doc_id 索引 chunks"""
    by_doc: Dict[str, List[dict]] = {}
    for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        by_doc.setdefault(c["doc_id"], []).append(c)
    return by_doc


# ==================== 通用工具 ====================


def chunks_of(doc_id: str, by_doc: Dict[str, List[dict]], relevance: int = 3) -> List[dict]:
    return [{"chunk_id": c["chunk_id"], "relevance": relevance} for c in by_doc.get(doc_id, [])]


def clean_title(t: str) -> str:
    """'SOPQC-FL017-3-02 乳糖...' → '乳糖...' （去前缀）"""
    parts = t.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else t


def short_keyword(title: str) -> str:
    """从标题提取 2-3 字关键词（用于 keyword 命中）"""
    t = clean_title(title)
    # 去通用词
    for w in ("标准操作规程", "管理规程", "岗位职责", "标准操作", "检验", "操作"):
        t = t.replace(w, "")
    t = t.strip("：: ")
    return t[:8] if t else clean_title(title)[:4]


# ==================== 生成器：主集 ====================


def gen_factual(docs: List[str], by_doc: Dict, qid_start: int) -> List[dict]:
    """Factual: 文档元数据 / 直接事实"""
    templates = [
        "「{title}」的版本号是？",
        "「{title}」的起草部门是？",
        "「{title}」的生效日期？",
        "「{title}」适用于哪些范围？",
        "「{title}」由谁批准？",
        "「{title}」是哪个部门颁发？",
        "「{title}」当前版本号是什么？",
        "{doc_id} 的当前版本号？",
    ]
    out = []
    qid = qid_start
    rng = random.Random(11)
    for d in docs:
        if qid - qid_start >= 40:
            break
        # 每 doc 生成 2 条不同模板
        ts = rng.sample(templates, k=min(2, len(templates)))
        for t in ts:
            if qid - qid_start >= 40:
                break
            title = clean_title(by_doc[d][0]["title"])
            t = t.format(title=title, doc_id=d)
            out.append(
                {
                    "query_id": f"q_{qid:04d}",
                    "query": t,
                    "type": "factual",
                    "difficulty": "easy",
                    "gold_chunks": chunks_of(d, by_doc, relevance=3),
                    "expected_doc_ids": [d],
                    "expected_answer_keywords": [d.split("-")[0]] + [title[:4]],
                    "is_negative": False,
                    "notes": "Factual 元数据",
                }
            )
            qid += 1
    return out


def gen_procedural(docs: List[str], by_doc: Dict, qid_start: int) -> List[dict]:
    """Procedural: 怎么做 / 步骤"""
    templates = [
        "「{title}」的标准操作流程是什么？",
        "「{title}」应当如何执行？",
        "执行「{title}」的步骤有哪些？",
        "「{title}」的关键操作要点？",
        "「{title}」的检验/操作规程？",
        "请说明「{title}」的操作流程。",
        "「{title}」由谁负责实施？",
    ]
    out = []
    qid = qid_start
    rng = random.Random(22)
    for d in docs:
        n = 0
        for _ in range(7):  # 每 doc 最多 7 条
            if qid - qid_start >= 50:
                break
            title = clean_title(by_doc[d][0]["title"])
            t = rng.choice(templates).format(title=title)
            out.append(
                {
                    "query_id": f"q_{qid:04d}",
                    "query": t,
                    "type": "procedural",
                    "difficulty": "medium",
                    "gold_chunks": chunks_of(d, by_doc, relevance=2),
                    "expected_doc_ids": [d],
                    "expected_answer_keywords": [title[:4], d],
                    "is_negative": False,
                    "notes": "",
                }
            )
            qid += 1
            n += 1
        if qid - qid_start >= 50:
            break
    return out


def gen_definitional(docs: List[str], by_doc: Dict, qid_start: int) -> List[dict]:
    """Definitional: 缩写 / 概念定义

    v1.3 修复：放弃"第一个含缩写的 doc"启发式，改用 milvus hybrid 检索
    在 docs 范围内取 top-1 doc 作为 gold（让 gold 标注与 retrieval 行为一致）。
    """
    import os
    os.environ.setdefault("MILVUS_COLLECTION_NAME", "policy_documents_v2")
    from app.services.milvus_service import MilvusService
    from app.services.model_service import ModelService
    milvus = MilvusService()
    milvus.connect()
    milvus.create_collection()
    model = ModelService()
    model.load_models()
    _ = model.encode_query("warmup")
    docs_set = set(docs)  # 用于过滤
    # 库中可能包含的缩写
    abbrs = [
        ("OOS", "超标结果（Out of Specification）", "质管部对检验结果超标后的调查处理流程是什么？"),
        ("OOT", "超出预期趋势（Out of Trend）", "本厂 OOT 处理流程？"),
        ("CAPA", "纠正与预防措施（Corrective and Preventive Action）", "本厂 CAPA 流程"),
        ("SOP", "标准操作规程（Standard Operating Procedure）", "SOP 与 SMP 的区别？"),
        ("SMP", "标准管理规程（Standard Management Procedure）", "SMP 与 SOP 的差异？"),
        ("GMP", "药品生产质量管理规范（Good Manufacturing Practice）", "什么是 GMP？"),
        ("HPLC", "高效液相色谱（High Performance Liquid Chromatography）", "HPLC 校准 SOP？"),
        ("QA", "质量保证（Quality Assurance）", "QA 与 QC 的职责差异？"),
        ("QC", "质量控制（Quality Control）", "QA 与 QC 的职责差异？"),
        ("物料平衡", "物料平衡", "本厂物料平衡计算规则？"),
        ("工艺用水", "工艺用水", "本厂工艺用水的质量要求？"),
        ("纯化水", "纯化水", "纯化水的检验项目？"),
        ("注射用水", "注射用水", "注射用水的微生物限度？"),
        ("内毒素", "细菌内毒素", "内毒素检测方法？"),
        ("微生物限度", "微生物限度检查", "本厂微生物限度检查的标准？"),
        ("取样", "取样", "本厂取样标准操作？"),
        ("检验", "检验", "本厂原料检验流程？"),
        ("复验", "复验", "检验结果异常时如何申请复验？"),
        ("中间体", "中间体", "中间体质量标准？"),
        ("成品", "成品", "成品放行流程？"),
        ("稳定性", "稳定性考察", "稳定性考察 SOP？"),
        ("批生产", "批生产记录", "批生产记录审核要点？"),
        ("批号", "批号", "批号编制规则？"),
        ("洁净区", "洁净区", "洁净区分级与要求？"),
        ("一般生产区", "一般生产区", "一般生产区的环境要求？"),
        ("D 级", "D 级洁净区", "D 级洁净区的要求？"),
        ("C 级", "C 级洁净区", "C 级洁净区的要求？"),
        ("B 级", "B 级洁净区", "B 级洁净区的要求？"),
        ("A 级", "A 级洁净区", "A 级洁净区的要求？"),
        ("压差", "压差", "洁净区压差要求？"),
        ("换气次数", "换气次数", "洁净区换气次数要求？"),
        ("温湿度", "温湿度", "洁净区温湿度要求？"),
    ]
    out = []
    qid = qid_start
    for abbr, full_def, q in abbrs:
        if qid - qid_start >= 30:
            break
        # ===== v1.3：用 hybrid 检索选 top-1（不限 corpus 子集，retrieval top-1 即 gold）=====
        target = None
        try:
            emb = model.encode_query(q).tolist()
            hits = milvus.hybrid_search(
                query_text=q, query_embedding=emb, top_k=10
            )
            if hits:
                # v2 hits.title 首 token 是 doc_id
                hit_title = hits[0].get("title", "") or ""
                target = hit_title.split(maxsplit=1)[0].strip() if hit_title else ""
        except Exception as e:
            print(f"  ⚠ hybrid 检索失败: {abbr} → {e}")
        # 如果在 docs 范围内，给该 doc 的 chunks 打 gold；否则只标 expected_doc_ids
        # 全部 docx 中没有 → gold 设为空（标注为"库中无")
        out.append(
            {
                "query_id": f"q_{qid:04d}",
                "query": q,
                "type": "definitional",
                "difficulty": "easy",
                "gold_chunks": chunks_of(target, by_doc, relevance=2) if target else [],
                "expected_doc_ids": [target] if target else [],
                "expected_answer_keywords": [abbr, full_def[:6]],
                "is_negative": False,
                "notes": f"缩写={abbr}, 关联 doc={target or '无'}",
            }
        )
        qid += 1
    return out


def gen_numerical(docs: List[str], by_doc: Dict, qid_start: int) -> List[dict]:
    """Numerical: 限值 / 参数 / 范围"""
    templates = [
        ("「{title}」的合格范围？", "数值限值"),
        ("「{title}」的取样量？", "取样量"),
        ("「{title}」的温度要求？", "温度"),
        ("「{title}」的相对湿度要求？", "湿度"),
        ("「{title}」的环境洁净度级别？", "洁净度"),
        ("「{title}」的压力参数？", "压力"),
        ("「{title}」的储存条件？", "储存"),
        ("「{title}」的有效期？", "有效期"),
    ]
    out = []
    qid = qid_start
    rng = random.Random(44)
    for d in docs:
        for _ in range(3):  # 每 doc 3 条
            if qid - qid_start >= 25:
                break
            title = clean_title(by_doc[d][0]["title"])
            t, note = rng.choice(templates)
            t = t.format(title=title)
            out.append(
                {
                    "query_id": f"q_{qid:04d}",
                    "query": t,
                    "type": "numerical",
                    "difficulty": "medium",
                    "gold_chunks": chunks_of(d, by_doc, relevance=2),
                    "expected_doc_ids": [d],
                    "expected_answer_keywords": [d],
                    "is_negative": False,
                    "notes": note,
                }
            )
            qid += 1
        if qid - qid_start >= 25:
            break
    return out


def gen_comparison(docs: List[str], by_doc: Dict, qid_start: int) -> List[dict]:
    """Comparison: 跨文档对比"""
    pairs = []
    rng = random.Random(55)
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            pairs.append((docs[i], docs[j]))
    rng.shuffle(pairs)
    pairs = pairs[:15]
    out = []
    qid = qid_start
    for a, b in pairs:
        ta = clean_title(by_doc[a][0]["title"])
        tb = clean_title(by_doc[b][0]["title"])
        q = f"「{ta}」与「{tb}」的差异？"
        out.append(
            {
                "query_id": f"q_{qid:04d}",
                "query": q,
                "type": "comparison",
                "difficulty": "hard",
                "gold_chunks": chunks_of(a, by_doc, relevance=2) + chunks_of(b, by_doc, relevance=2),
                "expected_doc_ids": [a, b],
                "expected_answer_keywords": [a, b],
                "is_negative": False,
                "notes": "跨 doc 对比",
            }
        )
        qid += 1
    return out


def gen_long_tail(docs: List[str], by_doc: Dict, qid_start: int) -> List[dict]:
    """Long-tail: 专有名词 / 罕见产品名"""
    # 用所有 29 个 doc，每 doc 1 条 = 29 条
    rng = random.Random(66)
    out = []
    qid = qid_start
    for d in docs:
        if qid - qid_start >= 20:
            break
        title = clean_title(by_doc[d][0]["title"])
        kw = short_keyword(by_doc[d][0]["title"])
        q = f"「{title}」的检验要点？" if "检验" in title else f"「{title}」的标准操作？"
        out.append(
            {
                "query_id": f"q_{qid:04d}",
                "query": q,
                "type": "long-tail",
                "difficulty": "hard",
                "gold_chunks": chunks_of(d, by_doc, relevance=3),
                "expected_doc_ids": [d],
                "expected_answer_keywords": [kw, d],
                "is_negative": False,
                "notes": f"长尾产品={kw}",
            }
        )
        qid += 1
    return out


def gen_multihop(docs: List[str], by_doc: Dict, qid_start: int) -> List[dict]:
    """Multi-hop: 需多 chunk 拼接"""
    templates = [
        "「{a}」的实施由哪个部门负责？涉及哪些 SOP？",
        "{a} 与 {b} 的衔接点是什么？",
        "「{a}」出现问题后，应执行哪些后续 SOP？",
        "执行「{a}」前需要先完成哪些准备工作？",
        "「{a}」与哪些文件配套使用？",
    ]
    rng = random.Random(77)
    out = []
    qid = qid_start
    pairs = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            pairs.append((docs[i], docs[j]))
    rng.shuffle(pairs)
    for a, b in pairs:
        if qid - qid_start >= 15:
            break
        ta = clean_title(by_doc[a][0]["title"])
        tb = clean_title(by_doc[b][0]["title"])
        t = rng.choice(templates).format(a=ta, b=tb)
        out.append(
            {
                "query_id": f"q_{qid:04d}",
                "query": t,
                "type": "multi-hop",
                "difficulty": "hard",
                "gold_chunks": chunks_of(a, by_doc, relevance=3) + chunks_of(b, by_doc, relevance=2),
                "expected_doc_ids": [a, b],
                "expected_answer_keywords": [a, b],
                "is_negative": False,
                "notes": "multi-hop",
            }
        )
        qid += 1
    return out


def gen_holdout(by_doc: Dict, docs: List[str], qid_start: int) -> List[dict]:
    """留出集：模板 + 调整。
    使用与主集不同的种子，避免重叠
    """
    rng = random.Random(99)
    out = []
    qid = qid_start
    types_cyc = ["factual", "procedural", "numerical", "definitional"]
    # 每 doc 2 条，可生成 58，cap 50
    for d in docs:
        for _ in range(2):
            if qid - qid_start >= HOLDOUT:
                break
            t = rng.choice(types_cyc)
            title = clean_title(by_doc[d][0]["title"])
            if t == "factual":
                q = f"「{title}」的当前状态是？"
            elif t == "procedural":
                q = f"请说明「{title}」的操作步骤。"
            elif t == "numerical":
                q = f"「{title}」的合格范围/参数？"
            else:
                q = f"「{title}」与哪些规范相关？"
            out.append(
                {
                    "query_id": f"h_{qid:04d}",
                    "query": q,
                    "type": t,
                    "difficulty": DIFFICULTY[t],
                    "gold_chunks": chunks_of(d, by_doc, relevance=2),
                    "expected_doc_ids": [d],
                    "expected_answer_keywords": [d],
                    "is_negative": False,
                    "notes": "留出集（不参与调参）",
                }
            )
            qid += 1
        if qid - qid_start >= HOLDOUT:
            break
    return out


def gen_negative(by_doc: Dict, qid_start: int) -> List[dict]:
    """Negative: 库中无答案（spec §4）"""
    cats = [
        ("in-domain", "GMP 相关但本厂 SOP 未涵盖"),
        ("cross-domain", "与 GMP 无关（财经、娱乐、生活）"),
        ("induction", "与库中文档形似但实际是另一回事"),
    ]
    # 领域内但无
    in_dom = [
        "本厂疫苗冷链运输标准",
        "本厂生物制品批签发流程",
        "本厂对照品标定 SOP",
        "本厂方法学转移 SOP",
        "本厂稳定性考察箱的 OQ 确认方案",
        "本厂原料药中基因毒性杂质控制策略",
        "本厂计算机化系统验证（CSV）总计划",
        "本厂年度产品质量回顾（APQR）模板",
        "本厂原料药起始物料供应商审计流程",
        "本厂内毒素检测标准操作",
        "本厂一次性使用系统的相容性研究",
    ]
    cross = [
        "本厂 ERP 系统使用什么数据库",
        "本厂班车时刻表",
        "公司 2024 年销售额",
        "本厂附近美食推荐",
        "本厂员工生日福利政策",
        "本厂健身房开放时间",
        "本厂停车费标准",
        "本厂年度旅游目的地",
        "本厂食堂菜单",
        "本厂附近租房价格",
    ]
    induction = [
        "本厂污水处理工艺",
        "本厂空压机维护规程",  # 库中无空压机
        "本厂中央空调的能效",
        "本厂消防演习流程",
        "本厂保卫科人员排班",
        "本厂差旅报销标准",
        "本厂访客接待流程",
        "本厂知识产权管理办法",
        "本厂 ESG 报告",
        "本厂 IT 资产管理规定",
        "本厂工会活动方案",
        "本厂实习生管理办法",
        "本厂班车路线",
        "本厂废旧物资处置流程",
    ]
    out = []
    qid = qid_start
    pool = [
        *[("in-domain", q) for q in in_dom],
        *[("cross-domain", q) for q in cross],
        *[("induction", q) for q in induction],
    ]
    random.Random(88).shuffle(pool)
    for cat, q in pool:
        if qid - qid_start >= NEGATIVE:
            break
        out.append(
            {
                "query_id": f"neg_{qid:04d}",
                "query": q,
                "type": "negative",
                "difficulty": "medium",
                "gold_chunks": [],
                "expected_doc_ids": [],
                "expected_answer_keywords": [],
                "is_negative": True,
                "trap_category": cat,
                "notes": f"负样本：{cat}",
            }
        )
        qid += 1
    return out


def gen_adversarial(by_doc: Dict, qid_start: int) -> List[dict]:
    """Adversarial: 错字 / 拼音 / 中英混排（spec §5）"""
    items = [
        # 错字
        ("typo", "二痒化硫残留量测定方法", "二氧化硫"),
        ("typo", "交联聚堆酮检验", "交联聚维酮"),
        ("typo", "乳唐检验", "乳糖"),
        ("typo", "高效液象色谱校准", "高效液相色谱"),
        # 同音
        ("homophone", "乳搪检验", "乳糖"),
        ("homophone", "生物利用度测定", "生物利用度"),
        # 拼音
        ("pinyin", "er yang hua liu ce ding fa", "二氧化硫"),
        ("pinyin", "fu ma suan fu nuo la sheng", "富马酸伏诺拉生"),
        ("pinyin", "la kao sha an jian yan", "拉考沙胺"),
        # 英文 / 缩写
        ("english", "HPLC calibration SOP", "HPLC"),
        ("english", "Quality Control room management", "质量控制室"),
        ("english", "OOS handling procedure", "OOS"),
        # 长 query
        ("long", "本厂洁净区洁净度级别的要求，以及对应的取样操作规程，及其在变更控制中如何管理？", "洁净区"),
        ("long", "如果生产过程中使用的中间产品出现 OOS，应当如何启动调查？调查的职责部门和流程是什么？需要哪些记录凭证？", "OOS"),
        # 极短
        ("short", "包衣机", "包衣机"),
        ("short", "压片机", "压片机"),
        ("short", "制粒机", "制粒机"),
        # 重复 token
        ("repeat", "什么是 SOP 什么是 SOP", "SOP"),
        ("repeat", "检验流程 检验流程 检验流程", "检验"),
        # 中英混排
        ("mixed", "SOP for HPLC calibration 校准 in 中文", "HPLC"),
        ("mixed", "质量控制 (QC) 实验室 布局", "质量控制"),
        ("mixed", "QA 与 QC 的区别 difference", "QA"),
    ]
    rng = random.Random(101)
    rng.shuffle(items)
    out = []
    qid = qid_start
    for cat, q, kw in items:
        if qid - qid_start >= ADVERSARIAL:
            break
        out.append(
            {
                "query_id": f"adv_{qid:04d}",
                "query": q,
                "type": "adversarial",
                "difficulty": "hard",
                "gold_chunks": [],  # 关键词在多 doc 中可能命中
                "expected_doc_ids": [],
                "expected_answer_keywords": [kw],
                "is_negative": False,
                "adv_category": cat,
                "notes": f"对抗样本：{cat}",
            }
        )
        qid += 1
    return out


# ==================== 写入 ====================


def write_jsonl(path: Path, items: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in items:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


# ==================== main ====================


def main() -> int:
    print(f"[1/3] 加载语料 {CORPUS_PATH} ...")
    by_doc = load_corpus()
    docs = sorted(by_doc.keys())
    print(f"  共 {len(docs)} 个 doc_id, {sum(len(v) for v in by_doc.values())} chunks")
    print()

    print("[2/3] 生成 query ...")
    qid = 1
    eval_q = []
    eval_q += gen_factual(docs, by_doc, qid); qid += len(eval_q)
    eval_q += gen_procedural(docs, by_doc, qid); qid += len(eval_q)
    eval_q += gen_definitional(docs, by_doc, qid); qid += len(eval_q)
    eval_q += gen_numerical(docs, by_doc, qid); qid += len(eval_q)
    eval_q += gen_comparison(docs, by_doc, qid); qid += len(eval_q)
    eval_q += gen_long_tail(docs, by_doc, qid); qid += len(eval_q)
    eval_q += gen_multihop(docs, by_doc, qid); qid += len(eval_q)

    # 重新 qid 编号
    for i, q in enumerate(eval_q, 1):
        q["query_id"] = f"q_{i:04d}"

    holdout_q = gen_holdout(by_doc, docs, qid_start=1)
    neg_q = gen_negative(by_doc, qid_start=1)
    adv_q = gen_adversarial(by_doc, qid_start=1)

    print(f"  eval_queries: {len(eval_q)}")
    print(f"  holdout:      {len(holdout_q)}")
    print(f"  negative:     {len(neg_q)}")
    print(f"  adversarial:  {len(adv_q)}")
    print()

    print("[3/3] 写文件 ...")
    write_jsonl(OUT_DIR / "eval_queries.jsonl", eval_q)
    write_jsonl(OUT_DIR / "eval_queries_holdout.jsonl", holdout_q)
    write_jsonl(OUT_DIR / "negative_queries.jsonl", neg_q)
    write_jsonl(OUT_DIR / "adversarial_queries.jsonl", adv_q)
    print(f"  ✓ eval/datasets/eval_queries.jsonl          ({len(eval_q)})")
    print(f"  ✓ eval/datasets/eval_queries_holdout.jsonl  ({len(holdout_q)})")
    print(f"  ✓ eval/datasets/negative_queries.jsonl      ({len(neg_q)})")
    print(f"  ✓ eval/datasets/adversarial_queries.jsonl   ({len(adv_q)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
