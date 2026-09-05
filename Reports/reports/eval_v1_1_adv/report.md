# S5 检索质量回归报告 (v1.1 harness)

- 生成时间: `2026-06-09T15:55:49`
- 评测 query 数: **22**
- 评测集合: `policy_documents_v2`（v1 → v2 已迁移）
- 模型: `./models/embedding/bge-large-zh-v1.5`
- 检索器: dense-only (nprobe=16) | hybrid (dense_limit=20, sparse_limit=20, rrf_k=60)
- 数据文件:
  - `eval/datasets/adversarial_queries.jsonl`
- 标准化测试语料（参考，未直接入检索）: `eval/datasets/eval_corpus.jsonl` (538 chunks)

## 1. Overall 指标

| 指标 | dense-only | hybrid | 相对提升 |
| --- | --- | --- | --- |
| Recall@10 | 0.0000 | 0.0000 | n/a |
| NDCG@10 | 0.7692 | 0.7537 | -2.0% |
| MRR | 0.0000 | 0.0000 | n/a |

| 延迟 | dense-only | hybrid | 备注 |
| --- | --- | --- | --- |
| p50 | 5.0ms | 3.4ms | - |
| p95 | 6.8ms | 3.9ms | ✓ 可接受 |

## 2. Query 来源分布

| 文件 | count |
| --- | --- |
| adversarial_queries.jsonl | 22 |

## 3. 按 query 类型

| 类型 | count | dense R | hybrid R | dense N | hybrid N | dense MRR | hybrid MRR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adversarial | 22 | 0.0000 | 0.0000 | 0.7692 | 0.7537 | 0.0000 | 0.0000 |

## 4. 按难度

| 难度 | count | dense R | hybrid R | dense N | hybrid N |
| --- | --- | --- | --- | --- | --- |
| hard | 22 | 0.0000 | 0.0000 | 0.7692 | 0.7537 |

## 5. Negative Query（库中无答案）

> 当前数据集中未包含 negative queries（仅主集），跳过此项。

## 6. Per-query 明细

| qid | type | is_neg | source | first gold doc | dense R@10 | hybrid R@10 | dense N@10 | hybrid N@10 | dense MRR | hybrid MRR | dense ms | hybrid ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adv_0001 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.73 | 0.51 | 0.00 | 0.00 | 5.7 | 3.3 |
| adv_0002 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.6 | 3.4 |
| adv_0003 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.95 | 0.99 | 0.00 | 0.00 | 6.5 | 3.4 |
| adv_0004 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.98 | 1.00 | 0.00 | 0.00 | 5.0 | 3.5 |
| adv_0005 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.50 | 0.93 | 0.00 | 0.00 | 6.8 | 3.7 |
| adv_0006 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.0 | 3.0 |
| adv_0007 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 0.69 | 0.00 | 0.00 | 7.3 | 4.4 |
| adv_0008 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.0 | 3.5 |
| adv_0009 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.8 | 3.7 |
| adv_0010 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.5 | 3.9 |
| adv_0011 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.9 | 3.8 |
| adv_0012 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.7 | 3.4 |
| adv_0013 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 0.69 | 0.00 | 0.00 | 3.8 | 3.2 |
| adv_0014 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.94 | 0.99 | 0.00 | 0.00 | 3.9 | 3.3 |
| adv_0015 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.92 | 0.96 | 0.00 | 0.00 | 4.3 | 3.1 |
| adv_0016 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.99 | 0.95 | 0.00 | 0.00 | 3.4 | 3.3 |
| adv_0017 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.97 | 0.91 | 0.00 | 0.00 | 5.6 | 3.3 |
| adv_0018 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.2 | 3.5 |
| adv_0019 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.8 | 3.5 |
| adv_0020 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.94 | 0.96 | 0.00 | 0.00 | 4.7 | 3.5 |
| adv_0021 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.4 | 2.8 |
| adv_0022 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.3 | 3.1 |
