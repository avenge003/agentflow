#!/usr/bin/env python3
"""G1 混合检索对比测试脚本

对比 dense-only（单路向量）与 hybrid（BM25 + dense + RRF）的检索质量与性能。

测试数据：policy_documents_v2（已迁移，5106 条 SOP 中文文档）
模型：models/embedding/bge-large-zh-v1.5

输出：
  - 每次查询的 dense top-K 与 hybrid top-K 对照
  - 关键词命中文档是否在 hybrid top-K 中出现
  - p50/p95 延迟
"""

import sys
import time
from typing import List, Dict, Any

sys.path.insert(0, ".")

# 测试时强制使用已迁移的 v2 集合（默认 settings 用的是 policy_documents v1）
import os
os.environ.setdefault("MILVUS_COLLECTION_NAME", "policy_documents_v2")

from app.core.config import settings
from app.services.milvus_service import MilvusService
from app.services.model_service import ModelService


SAMPLE_QUERIES = [
    {
        "query": "厂房设施管理规程",
        "expect": "BM25 强：精确词命中；dense 中等：标题语义相似",
    },
    {
        "query": "洁净区的空气洁净度要求",
        "expect": "BM25 强：洁净区/空气/洁净度 命中；dense 中等",
    },
    {
        "query": "生产车间应当如何防止交叉污染",
        "expect": "dense 强：语义；BM25 弱：句式化",
    },
    {
        "query": "取样区设置",
        "expect": "BM25 强：取样区；dense 中等",
    },
    {
        "query": "质量控制实验室布局",
        "expect": "BM25 中：实验室/质量；dense 中",
    },
]


def truncate(s: str, n: int = 60) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[:n] + "..."


def print_hits(label: str, hits: List[Dict[str, Any]], top: int = 5) -> None:
    print(f"  {label}（top {top}）:")
    if not hits:
        print("    (无结果)")
        return
    for i, h in enumerate(hits[:top], 1):
        print(
            f"    [{i}] score={h['score']:.4f}  "
            f"id={h['chunk_id']}  title={truncate(h.get('title'), 30)!r}"
        )


def main() -> int:
    print("=" * 70)
    print("G1 混合检索对比测试  v1.1.0")
    print("=" * 70)
    print(f"集合: {settings.milvus_collection_name}（已迁移 v2）")
    print(f"hybrid_dense_limit={settings.hybrid_dense_limit}, "
          f"hybrid_sparse_limit={settings.hybrid_sparse_limit}, "
          f"rrf_k={settings.rrf_k}")
    print()

    # 1) 加载服务
    print("[1/3] 初始化 MilvusService + ModelService ...", flush=True)
    t0 = time.perf_counter()
    milvus = MilvusService()
    milvus.connect()
    milvus.create_collection()
    model = ModelService()
    model.load_models()  # 显式加载 BGE
    print(f"  初始化耗时: {time.perf_counter() - t0:.1f}s")
    print()

    # 2) 预热（第一次推理会触发 JIT/懒加载）
    print("[2/3] 预热 embedding 模型 ...", flush=True)
    _ = model.encode_query("预热")
    print("  预热完成")
    print()

    # 3) 测试每个 query
    print("[3/3] 逐 query 检索对比", flush=True)
    dense_lats: List[float] = []
    hybrid_lats: List[float] = []

    for qi, q in enumerate(SAMPLE_QUERIES, 1):
        query = q["query"]
        print()
        print(f"--- Q{qi}: {query!r} ---")
        print(f"  预期: {q['expect']}")

        # 向量化
        t0 = time.perf_counter()
        emb = model.encode_query(query).tolist()
        emb_ms = (time.perf_counter() - t0) * 1000
        print(f"  embed: {emb_ms:.1f}ms (dim={len(emb)})")

        # dense-only
        t0 = time.perf_counter()
        dense_hits = milvus.search_documents(
            query_embedding=emb, top_k=5, score_threshold=0.0
        )
        dense_ms = (time.perf_counter() - t0) * 1000
        dense_lats.append(dense_ms)
        print(f"  dense: {dense_ms:.1f}ms")
        print_hits("dense-only", dense_hits)

        # hybrid
        t0 = time.perf_counter()
        hybrid_hits = milvus.hybrid_search(
            query_text=query, query_embedding=emb, top_k=5
        )
        hybrid_ms = (time.perf_counter() - t0) * 1000
        hybrid_lats.append(hybrid_ms)
        print(f"  hybrid: {hybrid_ms:.1f}ms")
        print_hits("hybrid    ", hybrid_hits)

        # 差异：title 集合对比
        d_titles = {h.get("title", "") for h in dense_hits}
        h_titles = {h.get("title", "") for h in hybrid_hits}
        if d_titles != h_titles:
            print(
                f"  ⚠  top-5 不一致："
                f"hybrid 新增 {len(h_titles - d_titles)}, "
                f"hybrid 减少 {len(d_titles - h_titles)}"
            )
        else:
            print("  ✓  top-5 完全一致")

    # 4) 汇总
    print()
    print("=" * 70)
    print("汇总")
    print("=" * 70)
    n = len(SAMPLE_QUERIES)
    if n:
        def pct(arr, p):
            arr = sorted(arr)
            if not arr:
                return 0.0
            k = max(0, min(len(arr) - 1, int(round((p / 100) * (len(arr) - 1)))))
            return arr[k]

        print(f"  dense  p50={pct(dense_lats, 50):.1f}ms  "
              f"p95={pct(dense_lats, 95):.1f}ms  "
              f"max={max(dense_lats):.1f}ms")
        print(f"  hybrid p50={pct(hybrid_lats, 50):.1f}ms  "
              f"p95={pct(hybrid_lats, 95):.1f}ms  "
              f"max={max(hybrid_lats):.1f}ms")
        ratio = sum(hybrid_lats) / max(sum(dense_lats), 1e-6)
        print(f"  hybrid/dense 平均耗时比: {ratio:.2f}x")
        print()
        if ratio > 1.5:
            print("  ⚠ hybrid 延迟偏高，建议：")
            print("     - 降低 hybrid_dense_limit / hybrid_sparse_limit")
            print("     - 或调小 RRF k")
        else:
            print("  ✓ hybrid 延迟在可接受范围（≤ dense × 1.5）")

    milvus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
