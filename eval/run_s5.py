#!/usr/bin/env python3
"""S5 检索质量回归评估 v1.1

适配 eval-data-v1.0 数据集（test_datasets.md 规范）

对比检索器：
  - dense-only (search_documents)
  - hybrid     (hybrid_search: BM25 + dense + RRF)

指标：
  - Recall@K   (rel>=2 出现在 top-K)
  - NDCG@K     (rel ∈ {0,1,2,3} 的折损累积增益)
  - MRR        (首个 rel>=2 的倒数排名)
  - Top-1 Hit  (top-1 是否 rel>=2)

标签规则（test_datasets.md §3.3 新 schema，兼容旧 schema）：
  rel=3  hit.chunk_id 命中任一 gold.chunk_id
         (回退：hit.title 以 gold_doc_prefix 起头)
  rel=2  hit.doc_id 命中任一 expected_doc_ids
         (回退：hit.content 含任一 gold_text_keyword)
  rel=1  hit.content/title 含任一 expected_answer_keywords
  rel=0  不相关

Negative queries：所有 hit 强制 rel=0；期望 top-1 rel=0
Adversarial queries：期望 rel>=1（关键词命中）
Holdout queries：与主集相同处理

数据文件（test_datasets.md §1）：
  eval_queries.jsonl              主集
  eval_queries_holdout.jsonl      留出集
  negative_queries.jsonl          负样本
  adversarial_queries.jsonl       对抗

用法：
  # 跑主集
  python eval/run_s5.py

  # 跑全部 4 类共 302 条
  python eval/run_s5.py --all

  # 跑指定文件（可多选）
  python eval/run_s5.py --queries eval/datasets/negative_queries.jsonl

  # 跑主集 + 负样本
  python eval/run_s5.py --queries eval/datasets/eval_queries.jsonl eval/datasets/negative_queries.jsonl

  # 指定 top-k 与报告目录
  python eval/run_s5.py --all --topk 10 --report-dir Reports/reports/eval_v1_1
"""

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# 测试时切到 v2 集合（spec 用真实生产集合跑基线）
os.environ.setdefault("MILVUS_COLLECTION_NAME", "policy_documents_v2")
sys.path.insert(0, ".")

from app.core.config import settings  # noqa: E402
from app.services.milvus_service import MilvusService  # noqa: E402
from app.services.model_service import ModelService  # noqa: E402


# ==================== 默认文件集（v1.0 数据集）====================

DEFAULT_QUERIES = "eval/datasets/eval_queries.jsonl"
ALL_FILES = [
    "eval/datasets/eval_queries.jsonl",
    "eval/datasets/eval_queries_holdout.jsonl",
    "eval/datasets/negative_queries.jsonl",
    "eval/datasets/adversarial_queries.jsonl",
]
CORPUS_PATH = "eval/datasets/eval_corpus.jsonl"


# ==================== 加载 ====================


def load_queries(paths: List[str]) -> List[Dict[str, Any]]:
    """支持多文件加载，每条 query 加 source 字段"""
    qs = []
    for p in paths:
        if not Path(p).exists():
            print(f"  ⚠ 文件不存在，跳过: {p}")
            continue
        n_before = len(qs)
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                q = json.loads(line)
                q["_source"] = Path(p).name
                qs.append(q)
        print(f"  ✓ {p}: {len(qs) - n_before} 条")
    return qs


# ==================== chunk_id 工具 ====================


def extract_doc_id(hit_or_chunk_id) -> str:
    """v1.2 适配：doc_id 优先从 hit.title 首 token 提取

    v2 集合里 chunk_id 是 Milvus INT64 主键（数字串），无语义。
    真实 doc_id 编码在 title 字段首 token（如 'SOPQC-FL017-3-02  标题...'）。
    兼容两种调用：
      - extract_doc_id(hit_dict)  ← 推荐
      - extract_doc_id("DOC::p0::c0")  ← 旧合成 ID 兼容
    """
    if isinstance(hit_or_chunk_id, dict):
        title = hit_or_chunk_id.get("title", "") or ""
        if title:
            first = title.split(maxsplit=1)[0].strip()
            if first:
                return first
        s = str(hit_or_chunk_id.get("chunk_id", "") or "")
    else:
        s = str(hit_or_chunk_id or "")
    if not s:
        return ""
    if "::" in s:
        return s.split("::", 1)[0]
    return ""


# ==================== 相关性判定（双 schema）====================


def compute_relevance(hit: Dict[str, Any], query: Dict[str, Any]) -> int:
    """按 gold 规则给 hit 打分，支持新/旧 schema 自动回退

    新 schema（test_datasets.md §3.3）：
      - gold_chunks: [{chunk_id, relevance}, ...]
      - expected_doc_ids: [str, ...]
      - expected_answer_keywords: [str, ...]
    旧 schema（兼容）：
      - gold_doc_prefixes: [str, ...]
      - gold_text_keywords: [str, ...]
    """
    is_neg = query.get("is_negative", False)
    if is_neg:
        return 0

    chunk_id = str(hit.get("chunk_id", "") or "")
    title = hit.get("title", "") or ""
    content = hit.get("content", "") or ""
    text_blob = title + "\n" + content

    # ===== 新 schema 优先 =====
    gold_chunks = query.get("gold_chunks") or []
    if gold_chunks:
        gold_ids = {g.get("chunk_id") for g in gold_chunks if g.get("chunk_id")}
        if chunk_id and chunk_id in gold_ids:
            return 3
        # 回退 1：gold 合成 chunk_id 'SOPQC-FL017-3-02::p0::c0' 形式
        #         vs v2 hits title 'SOPQC-FL017-3-02 ...' 形式 → 匹配 doc_id 部分
        gold_doc_id_set = set()
        for g in gold_chunks:
            cid = g.get("chunk_id", "") or ""
            if "::" in cid:
                gold_doc_id_set.add(cid.split("::", 1)[0])
        if gold_doc_id_set:
            hit_doc = extract_doc_id(hit)
            if hit_doc and hit_doc in gold_doc_id_set:
                return 3
    # doc_id 级（v1.2：从 title 提取）
    expected_doc_ids = query.get("expected_doc_ids") or []
    if expected_doc_ids:
        hit_doc = extract_doc_id(hit)
        if hit_doc and hit_doc in expected_doc_ids:
            return 2
    # 关键词弱相关
    expected_keywords = query.get("expected_answer_keywords") or []
    if expected_keywords:
        for kw in expected_keywords:
            if kw and kw in text_blob:
                return 1

    # ===== 旧 schema 回退 =====
    gold_prefixes = query.get("gold_doc_prefixes") or []
    if gold_prefixes:
        for p in gold_prefixes:
            if p and title.startswith(p):
                return 3
    gold_keywords = query.get("gold_text_keywords") or []
    if gold_keywords:
        for kw in gold_keywords:
            if kw and kw in text_blob:
                return 2

    return 0


# ==================== 指标 ====================


def dcg_at_k(rels: List[int], k: int) -> float:
    return sum(
        rel / math.log2(i + 2) for i, rel in enumerate(rels[:k]) if rel > 0
    )


def ndcg_at_k(rels: List[int], k: int) -> float:
    ideal = sorted(rels, reverse=True)[:k]
    idcg = dcg_at_k(ideal, k)
    if idcg == 0:
        return 0.0
    return dcg_at_k(rels, k) / idcg


def recall_at_k(rels: List[int], k: int, threshold: int = 2) -> float:
    return 1.0 if any(r >= threshold for r in rels[:k]) else 0.0


def mrr(rels: List[int], threshold: int = 2) -> float:
    for i, r in enumerate(rels, 1):
        if r >= threshold:
            return 1.0 / i
    return 0.0


# ==================== 评估主循环 ====================


def evaluate_one(
    milvus: MilvusService,
    model: ModelService,
    query: Dict[str, Any],
    top_k: int,
) -> Dict[str, Any]:
    q = query["query"]
    is_neg = query.get("is_negative", False)

    # embed
    emb = model.encode_query(q).tolist()

    # dense
    t0 = time.perf_counter()
    dense_hits = milvus.search_documents(
        query_embedding=emb, top_k=top_k, score_threshold=0.0
    )
    dense_ms = (time.perf_counter() - t0) * 1000

    # hybrid
    t0 = time.perf_counter()
    hybrid_hits = milvus.hybrid_search(
        query_text=q, query_embedding=emb, top_k=top_k
    )
    hybrid_ms = (time.perf_counter() - t0) * 1000

    def score(hits):
        rels = [compute_relevance(h, query) for h in hits]
        return {
            "rels": rels,
            "Recall@" + str(top_k): round(recall_at_k(rels, top_k), 4),
            "NDCG@" + str(top_k): round(ndcg_at_k(rels, top_k), 4),
            "MRR": round(mrr(rels), 4),
            "Top1_rel": rels[0] if rels else 0,
            "first_rel_rank": (
                next((i + 1 for i, r in enumerate(rels) if r >= 2), 0)
            ),
        }

    return {
        "query_id": query["query_id"],
        "query": q,
        "type": query.get("type", ""),
        "difficulty": query.get("difficulty", ""),
        "is_negative": is_neg,
        "is_adversarial": query.get("type") == "adversarial",
        "source": query.get("_source", ""),
        "gold_doc_ids": query.get("expected_doc_ids") or [],
        "gold_keywords": (
            query.get("expected_answer_keywords")
            or query.get("gold_text_keywords")
            or []
        ),
        "n_gold_chunks": len(query.get("gold_chunks") or []),
        "dense": {"latency_ms": round(dense_ms, 1), **score(dense_hits)},
        "hybrid": {"latency_ms": round(hybrid_ms, 1), **score(hybrid_hits)},
    }


# ==================== 汇总 ====================


def _safe_avg(rows, k):
    vals = [r[k] for r in rows]
    return round(sum(vals) / max(len(vals), 1), 4)


def aggregate(per_query: List[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
    keys = [f"Recall@{top_k}", f"NDCG@{top_k}", "MRR"]

    overall = {}
    for variant in ("dense", "hybrid"):
        for k in keys:
            overall[f"{variant}_{k}"] = _safe_avg([r[variant] for r in per_query], k)
        overall[f"{variant}_p50_ms"] = round(
            sorted([r[variant]["latency_ms"] for r in per_query])[
                len(per_query) // 2
            ],
            1,
        )
        overall[f"{variant}_p95_ms"] = round(
            sorted([r[variant]["latency_ms"] for r in per_query])[
                int(len(per_query) * 0.95)
            ],
            1,
        )

    # by type
    by_type: Dict[str, Dict[str, float]] = {}
    types = sorted({r["type"] for r in per_query if r["type"]})
    for t in types:
        rs = [r for r in per_query if r["type"] == t]
        by_type[t] = {"count": len(rs)}
        for variant in ("dense", "hybrid"):
            for k in keys:
                by_type[t][f"{variant}_{k}"] = _safe_avg([r[variant] for r in rs], k)

    # by difficulty
    by_diff: Dict[str, Dict[str, float]] = {}
    diffs = sorted({r["difficulty"] for r in per_query if r["difficulty"]})
    for d in diffs:
        rs = [r for r in per_query if r["difficulty"] == d]
        by_diff[d] = {"count": len(rs)}
        for variant in ("dense", "hybrid"):
            for k in keys:
                by_diff[d][f"{variant}_{k}"] = _safe_avg([r[variant] for r in rs], k)

    # by source
    by_src: Dict[str, int] = {}
    for r in per_query:
        by_src[r["source"]] = by_src.get(r["source"], 0) + 1

    # negative 专项
    neg_rows = [r for r in per_query if r["is_negative"]]
    neg: Dict[str, Optional[float]] = {}
    for variant in ("dense", "hybrid"):
        if neg_rows:
            top1_zero = sum(1 for r in neg_rows if r[variant]["Top1_rel"] == 0)
            neg[f"{variant}_top1_zero_rate"] = round(top1_zero / len(neg_rows), 4)
        else:
            neg[f"{variant}_top1_zero_rate"] = None

    # 提升
    improvement = {}
    for k in keys:
        d = overall[f"dense_{k}"]
        h = overall[f"hybrid_{k}"]
        if d > 0:
            improvement[k] = f"{(h - d) / d * 100:+.1f}%"
        else:
            improvement[k] = "n/a"

    return {
        "overall": overall,
        "by_type": by_type,
        "by_difficulty": by_diff,
        "by_source": by_src,
        "negative": neg,
        "improvement": improvement,
        "n_queries": len(per_query),
    }


# ==================== 报告输出 ====================


def _fmt(v, default="n/a"):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return f"{v:.4f}"
    return str(v)


def render_report(
    summary: Dict[str, Any],
    per_query: List[Dict[str, Any]],
    top_k: int,
    queries_files: List[str],
) -> str:
    lines = []
    lines.append("# S5 检索质量回归报告 (v1.1 harness)\n")
    lines.append(
        f"- 生成时间: `{datetime.now().isoformat(timespec='seconds')}`"
    )
    lines.append(f"- 评测 query 数: **{summary['n_queries']}**")
    lines.append(
        f"- 评测集合: `{settings.milvus_collection_name}`（v1 → v2 已迁移）"
    )
    lines.append(f"- 模型: `{settings.embedding_model_path}`")
    lines.append(
        f"- 检索器: dense-only (nprobe=16) | hybrid "
        f"(dense_limit={settings.hybrid_dense_limit}, "
        f"sparse_limit={settings.hybrid_sparse_limit}, "
        f"rrf_k={settings.rrf_k})"
    )
    lines.append("- 数据文件:")
    for f in queries_files:
        lines.append(f"  - `{f}`")
    if Path(CORPUS_PATH).exists():
        n_corpus = sum(1 for _ in open(CORPUS_PATH, encoding="utf-8"))
        lines.append(
            f"- 标准化测试语料（参考，未直接入检索）: `{CORPUS_PATH}` ({n_corpus} chunks)"
        )
    lines.append("")

    # Overall
    lines.append("## 1. Overall 指标\n")
    lines.append("| 指标 | dense-only | hybrid | 相对提升 |")
    lines.append("| --- | --- | --- | --- |")
    for k in [f"Recall@{top_k}", f"NDCG@{top_k}", "MRR"]:
        d = summary["overall"][f"dense_{k}"]
        h = summary["overall"][f"hybrid_{k}"]
        imp = summary["improvement"][k]
        lines.append(f"| {k} | {d:.4f} | {h:.4f} | {imp} |")
    lines.append("")
    lines.append("| 延迟 | dense-only | hybrid | 备注 |")
    lines.append("| --- | --- | --- | --- |")
    lines.append(
        f"| p50 | {summary['overall']['dense_p50_ms']}ms | "
        f"{summary['overall']['hybrid_p50_ms']}ms | - |"
    )
    p95_d = summary['overall']['dense_p95_ms']
    p95_h = summary['overall']['hybrid_p95_ms']
    p95_note = '⚠ hybrid 较慢' if p95_h > p95_d * 1.5 else '✓ 可接受'
    lines.append(f"| p95 | {p95_d}ms | {p95_h}ms | {p95_note} |")
    lines.append("")

    # 来源分布
    lines.append("## 2. Query 来源分布\n")
    lines.append("| 文件 | count |")
    lines.append("| --- | --- |")
    for src, n in sorted(summary["by_source"].items()):
        lines.append(f"| {src} | {n} |")
    lines.append("")

    # 按类型
    lines.append("## 3. 按 query 类型\n")
    lines.append("| 类型 | count | dense R | hybrid R | dense N | hybrid N | dense MRR | hybrid MRR |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for t, m in summary["by_type"].items():
        lines.append(
            f"| {t} | {m['count']} | {m[f'dense_Recall@{top_k}']:.4f} | "
            f"{m[f'hybrid_Recall@{top_k}']:.4f} | "
            f"{m[f'dense_NDCG@{top_k}']:.4f} | {m[f'hybrid_NDCG@{top_k}']:.4f} | "
            f"{m['dense_MRR']:.4f} | {m['hybrid_MRR']:.4f} |"
        )
    lines.append("")

    # 按难度
    lines.append("## 4. 按难度\n")
    lines.append("| 难度 | count | dense R | hybrid R | dense N | hybrid N |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for d_, m in summary["by_difficulty"].items():
        lines.append(
            f"| {d_} | {m['count']} | {m[f'dense_Recall@{top_k}']:.4f} | "
            f"{m[f'hybrid_Recall@{top_k}']:.4f} | "
            f"{m[f'dense_NDCG@{top_k}']:.4f} | {m[f'hybrid_NDCG@{top_k}']:.4f} |"
        )
    lines.append("")

    # Negative
    lines.append("## 5. Negative Query（库中无答案）\n")
    n_neg = sum(1 for r in per_query if r["is_negative"])
    if n_neg > 0:
        lines.append(f"Top-1 rel=0 占比（越高 = 越少误召，n={n_neg}）：\n")
        lines.append("| 检索器 | top-1 zero 占比 |")
        lines.append("| --- | --- |")
        lines.append(
            f"| dense-only | {_fmt(summary['negative']['dense_top1_zero_rate'])} |"
        )
        lines.append(
            f"| hybrid    | {_fmt(summary['negative']['hybrid_top1_zero_rate'])} |"
        )
    else:
        lines.append("> 当前数据集中未包含 negative queries（仅主集），跳过此项。")
    lines.append("")

    # Per-query 表
    lines.append("## 6. Per-query 明细\n")
    lines.append(
        f"| qid | type | is_neg | source | first gold doc | "
        f"dense R@{top_k} | hybrid R@{top_k} | "
        f"dense N@{top_k} | hybrid N@{top_k} | "
        f"dense MRR | hybrid MRR | dense ms | hybrid ms |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    )
    for r in per_query:
        first_gold = r["gold_doc_ids"][0] if r["gold_doc_ids"] else "—"
        is_neg_mark = "✓" if r["is_negative"] else ""
        lines.append(
            f"| {r['query_id']} | {r['type']} | {is_neg_mark} | {r['source']} | "
            f"{first_gold} | "
            f"{r['dense'][f'Recall@{top_k}']:.2f} | {r['hybrid'][f'Recall@{top_k}']:.2f} | "
            f"{r['dense'][f'NDCG@{top_k}']:.2f} | {r['hybrid'][f'NDCG@{top_k}']:.2f} | "
            f"{r['dense']['MRR']:.2f} | {r['hybrid']['MRR']:.2f} | "
            f"{r['dense']['latency_ms']} | {r['hybrid']['latency_ms']} |"
        )
    lines.append("")

    return "\n".join(lines)


# ==================== Config snapshot ====================


def snapshot_config(queries_files: List[str]) -> Dict[str, Any]:
    return {
        "app_version": settings.app_version,
        "embedding_model_path": settings.embedding_model_path,
        "embedding_dimension": settings.embedding_dimension,
        "use_fp16": settings.use_fp16,
        "milvus_collection_name": settings.milvus_collection_name,
        "enable_hybrid": settings.enable_hybrid,
        "hybrid_dense_limit": settings.hybrid_dense_limit,
        "hybrid_sparse_limit": settings.hybrid_sparse_limit,
        "rrf_k": settings.rrf_k,
        "default_top_k": settings.default_top_k,
        "queries_files": queries_files,
        "corpus_path": CORPUS_PATH if Path(CORPUS_PATH).exists() else None,
    }


# ==================== main ====================


def main() -> int:
    parser = argparse.ArgumentParser(description="S5 检索质量回归 (v1.1)")
    parser.add_argument(
        "--queries",
        nargs="+",
        default=[DEFAULT_QUERIES],
        help=f"query 文件（可多个）。默认: {DEFAULT_QUERIES}",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="加载 4 个标准文件（主集+留出+负样本+对抗）",
    )
    parser.add_argument("--topk", type=int, default=10, help="K for Recall@K/NDCG@K")
    parser.add_argument(
        "--report-dir",
        default=None,
        help="报告输出目录；不指定则不写文件",
    )
    args = parser.parse_args()

    queries_files = ALL_FILES if args.all else args.queries

    print("=" * 70)
    print(f"S5 检索质量回归 v1.1（K={args.topk}）")
    print("=" * 70)
    print(f"collection: {settings.milvus_collection_name}")
    print(f"query files: {len(queries_files)} 个")
    for f in queries_files:
        print(f"  - {f}")
    print()

    # 1) 加载
    print("[1/3] 加载 query ...")
    queries = load_queries(queries_files)
    print(f"  共 {len(queries)} 条\n")

    # 2) 初始化
    print("[2/3] 初始化服务 ...", flush=True)
    milvus = MilvusService()
    milvus.connect()
    milvus.create_collection()
    model = ModelService()
    model.load_models()
    _ = model.encode_query("预热")
    print("  预热完成\n")

    # 3) 逐 query 评估
    print("[3/3] 逐 query 评估 ...", flush=True)
    per_query = []
    t_all = time.perf_counter()
    for i, q in enumerate(queries, 1):
        t0 = time.perf_counter()
        r = evaluate_one(milvus, model, q, top_k=args.topk)
        per_query.append(r)
        dt = (time.perf_counter() - t0) * 1000
        if r["is_negative"]:
            sym = "n" if r["hybrid"]["Top1_rel"] == 0 else "x"
        elif r["is_adversarial"]:
            sym = "a"
        else:
            sym = "✓" if r["hybrid"][f"Recall@{args.topk}"] >= r["dense"][f"Recall@{args.topk}"] else "△"
        print(
            f"  [{i:3d}/{len(queries)}] {sym} {q['query_id']:8s} "
            f"dense R={r['dense'][f'Recall@{args.topk}']:.2f} "
            f"hybrid R={r['hybrid'][f'Recall@{args.topk}']:.2f} "
            f"({dt:.0f}ms)"
        )
    print(f"\n总耗时: {time.perf_counter() - t_all:.1f}s")
    print()

    # 4) 汇总
    summary = aggregate(per_query, top_k=args.topk)

    # 5) 输出报告
    md = render_report(summary, per_query, top_k=args.topk, queries_files=queries_files)
    print(md)

    # 6) 写文件
    if args.report_dir:
        rd = Path(args.report_dir)
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "report.md").write_text(md, encoding="utf-8")
        (rd / "per_query.json").write_text(
            json.dumps(per_query, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (rd / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (rd / "config_snapshot.json").write_text(
            json.dumps(snapshot_config(queries_files), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[报告已写入] {rd}/")
        print(f"  - report.md")
        print(f"  - per_query.json")
        print(f"  - summary.json")
        print(f"  - config_snapshot.json")

    milvus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
