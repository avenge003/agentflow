# S5 检索质量回归报告 (v1.1 harness)

- 生成时间: `2026-06-09T15:55:20`
- 评测 query 数: **35**
- 评测集合: `policy_documents_v2`（v1 → v2 已迁移）
- 模型: `./models/embedding/bge-large-zh-v1.5`
- 检索器: dense-only (nprobe=16) | hybrid (dense_limit=20, sparse_limit=20, rrf_k=60)
- 数据文件:
  - `eval/datasets/negative_queries.jsonl`
- 标准化测试语料（参考，未直接入检索）: `eval/datasets/eval_corpus.jsonl` (538 chunks)

## 1. Overall 指标

| 指标 | dense-only | hybrid | 相对提升 |
| --- | --- | --- | --- |
| Recall@10 | 0.0000 | 0.0000 | n/a |
| NDCG@10 | 0.0000 | 0.0000 | n/a |
| MRR | 0.0000 | 0.0000 | n/a |

| 延迟 | dense-only | hybrid | 备注 |
| --- | --- | --- | --- |
| p50 | 4.3ms | 3.4ms | - |
| p95 | 6.6ms | 4.0ms | ✓ 可接受 |

## 2. Query 来源分布

| 文件 | count |
| --- | --- |
| negative_queries.jsonl | 35 |

## 3. 按 query 类型

| 类型 | count | dense R | hybrid R | dense N | hybrid N | dense MRR | hybrid MRR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| negative | 35 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## 4. 按难度

| 难度 | count | dense R | hybrid R | dense N | hybrid N |
| --- | --- | --- | --- | --- | --- |
| medium | 35 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## 5. Negative Query（库中无答案）

Top-1 rel=0 占比（越高 = 越少误召，n=35）：

| 检索器 | top-1 zero 占比 |
| --- | --- |
| dense-only | 1.0000 |
| hybrid    | 1.0000 |

## 6. Per-query 明细

| qid | type | is_neg | source | first gold doc | dense R@10 | hybrid R@10 | dense N@10 | hybrid N@10 | dense MRR | hybrid MRR | dense ms | hybrid ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| neg_0001 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.7 | 3.5 |
| neg_0002 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.7 | 4.0 |
| neg_0003 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.2 | 3.4 |
| neg_0004 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 3.5 |
| neg_0005 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.1 | 3.4 |
| neg_0006 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.0 | 3.7 |
| neg_0007 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.3 | 3.4 |
| neg_0008 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 5.3 |
| neg_0009 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.8 | 3.4 |
| neg_0010 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.5 | 3.0 |
| neg_0011 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 3.7 |
| neg_0012 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.3 | 3.7 |
| neg_0013 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 3.7 |
| neg_0014 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.6 | 3.4 |
| neg_0015 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.5 | 3.7 |
| neg_0016 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 9.1 | 4.0 |
| neg_0017 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.0 | 3.3 |
| neg_0018 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.9 | 3.7 |
| neg_0019 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 3.3 |
| neg_0020 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 3.2 |
| neg_0021 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.1 | 3.1 |
| neg_0022 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.6 | 3.2 |
| neg_0023 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.5 | 3.6 |
| neg_0024 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 3.4 |
| neg_0025 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.9 | 3.8 |
| neg_0026 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.3 | 3.2 |
| neg_0027 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 3.6 |
| neg_0028 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.4 | 3.1 |
| neg_0029 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 3.4 |
| neg_0030 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.2 | 3.2 |
| neg_0031 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.5 | 3.1 |
| neg_0032 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.5 | 3.1 |
| neg_0033 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 3.2 |
| neg_0034 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.8 | 2.9 |
| neg_0035 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 3.3 |
