# S5 检索质量回归报告 (v1.1 harness)

- 生成时间: `2026-06-09T16:01:33`
- 评测 query 数: **302**
- 评测集合: `policy_documents_v2`（v1 → v2 已迁移）
- 模型: `./models/embedding/bge-large-zh-v1.5`
- 检索器: dense-only (nprobe=16) | hybrid (dense_limit=20, sparse_limit=20, rrf_k=60)
- 数据文件:
  - `eval/datasets/eval_queries.jsonl`
  - `eval/datasets/eval_queries_holdout.jsonl`
  - `eval/datasets/negative_queries.jsonl`
  - `eval/datasets/adversarial_queries.jsonl`
- 标准化测试语料（参考，未直接入检索）: `eval/datasets/eval_corpus.jsonl` (538 chunks)

## 1. Overall 指标

| 指标 | dense-only | hybrid | 相对提升 |
| --- | --- | --- | --- |
| Recall@10 | 0.0000 | 0.0000 | n/a |
| NDCG@10 | 0.6978 | 0.7249 | +3.9% |
| MRR | 0.0000 | 0.0000 | n/a |

| 延迟 | dense-only | hybrid | 备注 |
| --- | --- | --- | --- |
| p50 | 4.3ms | 3.4ms | - |
| p95 | 6.6ms | 4.2ms | ✓ 可接受 |

## 2. Query 来源分布

| 文件 | count |
| --- | --- |
| adversarial_queries.jsonl | 22 |
| eval_queries.jsonl | 195 |
| eval_queries_holdout.jsonl | 50 |
| negative_queries.jsonl | 35 |

## 3. 按 query 类型

| 类型 | count | dense R | hybrid R | dense N | hybrid N | dense MRR | hybrid MRR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adversarial | 22 | 0.0000 | 0.0000 | 0.7692 | 0.7537 | 0.0000 | 0.0000 |
| comparison | 15 | 0.0000 | 0.0000 | 0.7337 | 0.8042 | 0.0000 | 0.0000 |
| definitional | 44 | 0.0000 | 0.0000 | 0.7230 | 0.8214 | 0.0000 | 0.0000 |
| factual | 51 | 0.0000 | 0.0000 | 0.7782 | 0.7727 | 0.0000 | 0.0000 |
| long-tail | 20 | 0.0000 | 0.0000 | 0.8328 | 0.9088 | 0.0000 | 0.0000 |
| multi-hop | 15 | 0.0000 | 0.0000 | 0.8271 | 0.6883 | 0.0000 | 0.0000 |
| negative | 35 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| numerical | 32 | 0.0000 | 0.0000 | 0.6922 | 0.7461 | 0.0000 | 0.0000 |
| procedural | 68 | 0.0000 | 0.0000 | 0.8835 | 0.9167 | 0.0000 | 0.0000 |

## 4. 按难度

| 难度 | count | dense R | hybrid R | dense N | hybrid N |
| --- | --- | --- | --- | --- | --- |
| easy | 95 | 0.0000 | 0.0000 | 0.7527 | 0.7953 |
| hard | 72 | 0.0000 | 0.0000 | 0.7915 | 0.7937 |
| medium | 135 | 0.0000 | 0.0000 | 0.6091 | 0.6386 |

## 5. Negative Query（库中无答案）

Top-1 rel=0 占比（越高 = 越少误召，n=35）：

| 检索器 | top-1 zero 占比 |
| --- | --- |
| dense-only | 1.0000 |
| hybrid    | 1.0000 |

## 6. Per-query 明细

| qid | type | is_neg | source | first gold doc | dense R@10 | hybrid R@10 | dense N@10 | hybrid N@10 | dense MRR | hybrid MRR | dense ms | hybrid ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q_0001 | factual |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.0 | 3.3 |
| q_0002 | factual |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.94 | 0.88 | 0.00 | 0.00 | 3.7 | 3.1 |
| q_0003 | factual |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.5 | 3.1 |
| q_0004 | factual |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 1.00 | 0.88 | 0.00 | 0.00 | 9.6 | 5.0 |
| q_0005 | factual |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.98 | 1.00 | 0.00 | 0.00 | 6.2 | 3.4 |
| q_0006 | factual |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.81 | 0.96 | 0.00 | 0.00 | 3.7 | 3.6 |
| q_0007 | factual |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.5 | 3.3 |
| q_0008 | factual |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.87 | 0.99 | 0.00 | 0.00 | 6.6 | 3.1 |
| q_0009 | factual |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 0.98 | 1.00 | 0.00 | 0.00 | 3.6 | 3.8 |
| q_0010 | factual |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.8 | 3.4 |
| q_0011 | factual |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 0.00 | 0.33 | 0.00 | 0.00 | 3.5 | 3.0 |
| q_0012 | factual |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.9 | 3.5 |
| q_0013 | factual |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.96 | 0.89 | 0.00 | 0.00 | 4.8 | 4.0 |
| q_0014 | factual |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.96 | 0.89 | 0.00 | 0.00 | 5.6 | 3.7 |
| q_0015 | factual |  | eval_queries.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 1.00 | 0.43 | 0.00 | 0.00 | 3.7 | 3.5 |
| q_0016 | factual |  | eval_queries.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 0.79 | 0.50 | 0.00 | 0.00 | 4.3 | 3.6 |
| q_0017 | factual |  | eval_queries.jsonl | SMPVT001-3-00 | 0.00 | 0.00 | 1.00 | 0.84 | 0.00 | 0.00 | 3.3 | 3.2 |
| q_0018 | factual |  | eval_queries.jsonl | SMPVT001-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.9 | 3.3 |
| q_0019 | factual |  | eval_queries.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.63 | 0.95 | 0.00 | 0.00 | 3.7 | 3.1 |
| q_0020 | factual |  | eval_queries.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.75 | 0.98 | 0.00 | 0.00 | 4.6 | 4.4 |
| q_0021 | factual |  | eval_queries.jsonl | SOPQA004-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.8 | 3.6 |
| q_0022 | factual |  | eval_queries.jsonl | SOPQA004-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.7 | 3.6 |
| q_0023 | factual |  | eval_queries.jsonl | SOPQA008-3-02生产过程质量监控标准操作规程 | 0.00 | 0.00 | 0.54 | 0.50 | 0.00 | 0.00 | 3.7 | 3.4 |
| q_0024 | factual |  | eval_queries.jsonl | SOPQA008-3-02生产过程质量监控标准操作规程 | 0.00 | 0.00 | 0.82 | 0.89 | 0.00 | 0.00 | 3.5 | 3.4 |
| q_0025 | factual |  | eval_queries.jsonl | SOPQA010-3-00 | 0.00 | 0.00 | 0.85 | 0.89 | 0.00 | 0.00 | 3.7 | 3.6 |
| q_0026 | factual |  | eval_queries.jsonl | SOPQA010-3-00 | 0.00 | 0.00 | 0.98 | 1.00 | 0.00 | 0.00 | 3.7 | 3.3 |
| q_0027 | factual |  | eval_queries.jsonl | SOPQC-CP018-3-01 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.5 | 3.6 |
| q_0028 | factual |  | eval_queries.jsonl | SOPQC-CP018-3-01 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.6 | 3.5 |
| q_0029 | factual |  | eval_queries.jsonl | SOPQC-CP028-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.6 | 3.6 |
| q_0030 | factual |  | eval_queries.jsonl | SOPQC-CP028-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.3 | 4.1 |
| q_0031 | factual |  | eval_queries.jsonl | SOPQC-FL007-3-03 | 0.00 | 0.00 | 0.84 | 0.58 | 0.00 | 0.00 | 3.1 | 3.1 |
| q_0032 | factual |  | eval_queries.jsonl | SOPQC-FL007-3-03 | 0.00 | 0.00 | 0.95 | 0.99 | 0.00 | 0.00 | 3.6 | 3.2 |
| q_0033 | factual |  | eval_queries.jsonl | SOPQC-FL017-3-02 | 0.00 | 0.00 | 0.76 | 0.50 | 0.00 | 0.00 | 3.3 | 3.1 |
| q_0034 | factual |  | eval_queries.jsonl | SOPQC-FL017-3-02 | 0.00 | 0.00 | 0.63 | 0.36 | 0.00 | 0.00 | 4.2 | 3.5 |
| q_0035 | factual |  | eval_queries.jsonl | SOPQC-FL045-3-01 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.9 | 4.2 |
| q_0036 | factual |  | eval_queries.jsonl | SOPQC-FL045-3-01 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.5 | 3.6 |
| q_0037 | factual |  | eval_queries.jsonl | SOPQC-TZ049-3-00 | 0.00 | 0.00 | 0.94 | 0.98 | 0.00 | 0.00 | 3.7 | 4.3 |
| q_0038 | factual |  | eval_queries.jsonl | SOPQC-TZ049-3-00 | 0.00 | 0.00 | 0.95 | 0.95 | 0.00 | 0.00 | 3.6 | 3.3 |
| q_0039 | factual |  | eval_queries.jsonl | SOPQC-TZ054-3-01 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.6 | 3.6 |
| q_0040 | factual |  | eval_queries.jsonl | SOPQC-TZ054-3-01 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.5 | 3.7 |
| q_0041 | procedural |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.93 | 0.97 | 0.00 | 0.00 | 4.0 | 3.3 |
| q_0042 | procedural |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.93 | 0.97 | 0.00 | 0.00 | 4.7 | 3.3 |
| q_0043 | procedural |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.94 | 0.97 | 0.00 | 0.00 | 5.6 | 3.3 |
| q_0044 | procedural |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.96 | 0.99 | 0.00 | 0.00 | 3.8 | 3.6 |
| q_0045 | procedural |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.95 | 0.96 | 0.00 | 0.00 | 3.4 | 3.3 |
| q_0046 | procedural |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.93 | 0.97 | 0.00 | 0.00 | 5.4 | 3.8 |
| q_0047 | procedural |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.94 | 0.96 | 0.00 | 0.00 | 6.4 | 3.0 |
| q_0048 | procedural |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.88 | 0.81 | 0.00 | 0.00 | 5.5 | 3.4 |
| q_0049 | procedural |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.88 | 0.83 | 0.00 | 0.00 | 4.7 | 3.6 |
| q_0050 | procedural |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.88 | 0.83 | 0.00 | 0.00 | 6.2 | 3.1 |
| q_0051 | procedural |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.92 | 0.83 | 0.00 | 0.00 | 4.3 | 3.0 |
| q_0052 | procedural |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 1.00 | 0.88 | 0.00 | 0.00 | 6.0 | 2.9 |
| q_0053 | procedural |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.88 | 0.81 | 0.00 | 0.00 | 3.6 | 3.3 |
| q_0054 | procedural |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.92 | 0.83 | 0.00 | 0.00 | 3.8 | 3.3 |
| q_0055 | procedural |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.92 | 0.98 | 0.00 | 0.00 | 3.3 | 3.2 |
| q_0056 | procedural |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.79 | 0.95 | 0.00 | 0.00 | 3.7 | 3.0 |
| q_0057 | procedural |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.92 | 0.98 | 0.00 | 0.00 | 3.4 | 3.3 |
| q_0058 | procedural |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.00 | 0.69 | 0.00 | 0.00 | 6.0 | 3.1 |
| q_0059 | procedural |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.91 | 0.99 | 0.00 | 0.00 | 5.5 | 2.9 |
| q_0060 | procedural |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.00 | 0.69 | 0.00 | 0.00 | 3.9 | 3.6 |
| q_0061 | procedural |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.91 | 0.98 | 0.00 | 0.00 | 3.7 | 3.9 |
| q_0062 | procedural |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.90 | 0.98 | 0.00 | 0.00 | 6.5 | 2.9 |
| q_0063 | procedural |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.98 | 0.99 | 0.00 | 0.00 | 3.6 | 3.5 |
| q_0064 | procedural |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.90 | 0.98 | 0.00 | 0.00 | 4.1 | 3.5 |
| q_0065 | procedural |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.90 | 1.00 | 0.00 | 0.00 | 4.5 | 3.2 |
| q_0066 | procedural |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.89 | 0.99 | 0.00 | 0.00 | 5.7 | 3.0 |
| q_0067 | procedural |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.90 | 1.00 | 0.00 | 0.00 | 3.5 | 3.2 |
| q_0068 | procedural |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.89 | 0.99 | 0.00 | 0.00 | 4.1 | 3.5 |
| q_0069 | procedural |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.0 | 3.3 |
| q_0070 | procedural |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.1 | 3.4 |
| q_0071 | procedural |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.4 | 3.1 |
| q_0072 | procedural |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.8 | 3.2 |
| q_0073 | procedural |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.4 | 3.3 |
| q_0074 | procedural |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.2 | 3.3 |
| q_0075 | procedural |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.0 | 3.4 |
| q_0076 | procedural |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.6 | 3.7 |
| q_0077 | procedural |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.9 | 3.1 |
| q_0078 | procedural |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.7 | 3.1 |
| q_0079 | procedural |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.8 | 3.1 |
| q_0080 | procedural |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.5 | 4.4 |
| q_0081 | procedural |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.9 | 3.5 |
| q_0082 | procedural |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.8 | 3.1 |
| q_0083 | procedural |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.91 | 0.90 | 0.00 | 0.00 | 3.8 | 3.4 |
| q_0084 | procedural |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.97 | 0.90 | 0.00 | 0.00 | 3.5 | 3.6 |
| q_0085 | procedural |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.91 | 0.90 | 0.00 | 0.00 | 5.4 | 3.4 |
| q_0086 | procedural |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.91 | 0.90 | 0.00 | 0.00 | 6.0 | 3.5 |
| q_0087 | procedural |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.95 | 0.89 | 0.00 | 0.00 | 5.8 | 3.3 |
| q_0088 | procedural |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.91 | 0.88 | 0.00 | 0.00 | 4.0 | 3.6 |
| q_0089 | procedural |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.91 | 0.90 | 0.00 | 0.00 | 3.7 | 4.1 |
| q_0090 | procedural |  | eval_queries.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 0.77 | 0.45 | 0.00 | 0.00 | 4.0 | 3.5 |
| q_0091 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.86 | 0.90 | 0.00 | 0.00 | 3.9 | 3.8 |
| q_0092 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.94 | 0.98 | 0.00 | 0.00 | 5.0 | 3.1 |
| q_0093 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.80 | 0.96 | 0.00 | 0.00 | 5.7 | 3.3 |
| q_0094 | definitional |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.2 | 3.4 |
| q_0095 | definitional |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.96 | 0.99 | 0.00 | 0.00 | 3.6 | 3.0 |
| q_0096 | definitional |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 1.00 | 0.99 | 0.00 | 0.00 | 4.9 | 3.2 |
| q_0097 | definitional |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.88 | 0.97 | 0.00 | 0.00 | 6.8 | 3.2 |
| q_0098 | definitional |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.99 | 0.80 | 0.00 | 0.00 | 4.0 | 3.2 |
| q_0099 | definitional |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.60 | 0.96 | 0.00 | 0.00 | 3.9 | 3.1 |
| q_0100 | definitional |  | eval_queries.jsonl | SOPQA008-3-02生产过程质量监控标准操作规程 | 0.00 | 0.00 | 0.97 | 0.95 | 0.00 | 0.00 | 4.9 | 3.2 |
| q_0101 | definitional |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.00 | 0.87 | 0.00 | 0.00 | 3.5 | 3.3 |
| q_0102 | definitional |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.99 | 1.00 | 0.00 | 0.00 | 5.0 | 3.5 |
| q_0103 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.8 | 3.5 |
| q_0104 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 3.3 |
| q_0105 | definitional |  | eval_queries.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.99 | 1.00 | 0.00 | 0.00 | 5.1 | 4.3 |
| q_0106 | definitional |  | eval_queries.jsonl | SMPVT001-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.8 | 3.7 |
| q_0107 | definitional |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.92 | 0.97 | 0.00 | 0.00 | 3.6 | 3.6 |
| q_0108 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.57 | 0.93 | 0.00 | 0.00 | 3.7 | 3.5 |
| q_0109 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.92 | 0.00 | 0.00 | 6.5 | 3.6 |
| q_0110 | definitional |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.96 | 1.00 | 0.00 | 0.00 | 3.7 | 3.3 |
| q_0111 | definitional |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.7 | 3.5 |
| q_0112 | definitional |  | eval_queries.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 0.92 | 1.00 | 0.00 | 0.00 | 3.9 | 3.1 |
| q_0113 | definitional |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 1.00 | 0.99 | 0.00 | 0.00 | 4.4 | 3.1 |
| q_0114 | definitional |  | eval_queries.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.3 | 3.1 |
| q_0115 | definitional |  | eval_queries.jsonl | SOPWS010-3-00 | 0.00 | 0.00 | 0.00 | 0.94 | 0.00 | 0.00 | 6.5 | 3.2 |
| q_0116 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.50 | 0.00 | 0.00 | 5.1 | 3.1 |
| q_0117 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.39 | 0.00 | 0.00 | 6.9 | 3.0 |
| q_0118 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.8 | 3.3 |
| q_0119 | definitional |  | eval_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 3.2 |
| q_0120 | definitional |  | eval_queries.jsonl | SOPQA008-3-02生产过程质量监控标准操作规程 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.7 | 3.6 |
| q_0121 | numerical |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.2 | 3.9 |
| q_0122 | numerical |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.63 | 1.00 | 0.00 | 0.00 | 4.4 | 4.0 |
| q_0123 | numerical |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.8 | 3.4 |
| q_0124 | numerical |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.5 | 3.1 |
| q_0125 | numerical |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.00 | 0.63 | 0.00 | 0.00 | 6.6 | 3.4 |
| q_0126 | numerical |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.00 | 0.50 | 0.00 | 0.00 | 6.9 | 3.4 |
| q_0127 | numerical |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.81 | 0.83 | 0.00 | 0.00 | 5.6 | 3.0 |
| q_0128 | numerical |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.00 | 0.68 | 0.00 | 0.00 | 6.0 | 3.3 |
| q_0129 | numerical |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.00 | 0.68 | 0.00 | 0.00 | 4.1 | 3.4 |
| q_0130 | numerical |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.88 | 0.92 | 0.00 | 0.00 | 3.5 | 3.2 |
| q_0131 | numerical |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.82 | 1.00 | 0.00 | 0.00 | 3.3 | 3.3 |
| q_0132 | numerical |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.4 | 3.6 |
| q_0133 | numerical |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 0.96 | 0.97 | 0.00 | 0.00 | 3.5 | 3.2 |
| q_0134 | numerical |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 0.99 | 0.89 | 0.00 | 0.00 | 3.4 | 3.4 |
| q_0135 | numerical |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 0.99 | 0.89 | 0.00 | 0.00 | 4.1 | 3.0 |
| q_0136 | numerical |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 0.95 | 0.98 | 0.00 | 0.00 | 3.6 | 3.4 |
| q_0137 | numerical |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 0.95 | 0.98 | 0.00 | 0.00 | 4.3 | 3.3 |
| q_0138 | numerical |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 0.97 | 0.98 | 0.00 | 0.00 | 5.0 | 3.6 |
| q_0139 | numerical |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.93 | 0.86 | 0.00 | 0.00 | 5.2 | 3.8 |
| q_0140 | numerical |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.85 | 0.92 | 0.00 | 0.00 | 4.7 | 3.2 |
| q_0141 | numerical |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.92 | 0.91 | 0.00 | 0.00 | 4.6 | 3.6 |
| q_0142 | numerical |  | eval_queries.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.3 | 3.6 |
| q_0143 | numerical |  | eval_queries.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.6 | 3.4 |
| q_0144 | numerical |  | eval_queries.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.8 | 3.3 |
| q_0145 | numerical |  | eval_queries.jsonl | SMPVT001-3-00 | 0.00 | 0.00 | 0.83 | 0.42 | 0.00 | 0.00 | 3.8 | 5.7 |
| q_0146 | comparison |  | eval_queries.jsonl | SOPQC-FL045-3-01 | 0.00 | 0.00 | 0.50 | 0.76 | 0.00 | 0.00 | 3.7 | 3.4 |
| q_0147 | comparison |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.95 | 0.84 | 0.00 | 0.00 | 6.4 | 3.1 |
| q_0148 | comparison |  | eval_queries.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.87 | 0.93 | 0.00 | 0.00 | 5.7 | 3.5 |
| q_0149 | comparison |  | eval_queries.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.85 | 1.00 | 0.00 | 0.00 | 5.2 | 3.4 |
| q_0150 | comparison |  | eval_queries.jsonl | SOPSC-SB027-3-00 | 0.00 | 0.00 | 0.85 | 0.54 | 0.00 | 0.00 | 7.0 | 5.7 |
| q_0151 | comparison |  | eval_queries.jsonl | SOPQA010-3-00 | 0.00 | 0.00 | 0.45 | 0.50 | 0.00 | 0.00 | 6.6 | 3.6 |
| q_0152 | comparison |  | eval_queries.jsonl | SOPQC-TZ049-3-00 | 0.00 | 0.00 | 0.63 | 0.57 | 0.00 | 0.00 | 5.9 | 3.6 |
| q_0153 | comparison |  | eval_queries.jsonl | SOPQC-CP028-3-02 | 0.00 | 0.00 | 0.67 | 0.68 | 0.00 | 0.00 | 5.7 | 3.3 |
| q_0154 | comparison |  | eval_queries.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 0.43 | 0.50 | 0.00 | 0.00 | 5.5 | 3.5 |
| q_0155 | comparison |  | eval_queries.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.50 | 1.00 | 0.00 | 0.00 | 3.8 | 3.9 |
| q_0156 | comparison |  | eval_queries.jsonl | SOPQC-TZ054-3-01 | 0.00 | 0.00 | 0.95 | 0.96 | 0.00 | 0.00 | 4.5 | 3.6 |
| q_0157 | comparison |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.91 | 0.94 | 0.00 | 0.00 | 4.1 | 3.8 |
| q_0158 | comparison |  | eval_queries.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.56 | 0.87 | 0.00 | 0.00 | 5.7 | 4.1 |
| q_0159 | comparison |  | eval_queries.jsonl | SOPQC-TZ049-3-00 | 0.00 | 0.00 | 0.88 | 0.97 | 0.00 | 0.00 | 4.5 | 4.7 |
| q_0160 | comparison |  | eval_queries.jsonl | SOPQC-TZ063-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.0 | 3.8 |
| q_0161 | long-tail |  | eval_queries.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 0.95 | 0.95 | 0.00 | 0.00 | 5.2 | 3.6 |
| q_0162 | long-tail |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.92 | 0.82 | 0.00 | 0.00 | 3.7 | 3.3 |
| q_0163 | long-tail |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.00 | 0.86 | 0.00 | 0.00 | 4.7 | 3.3 |
| q_0164 | long-tail |  | eval_queries.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.92 | 1.00 | 0.00 | 0.00 | 4.4 | 3.6 |
| q_0165 | long-tail |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 0.99 | 0.90 | 0.00 | 0.00 | 4.8 | 3.8 |
| q_0166 | long-tail |  | eval_queries.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 0.97 | 0.95 | 0.00 | 0.00 | 3.5 | 3.4 |
| q_0167 | long-tail |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.88 | 0.88 | 0.00 | 0.00 | 4.1 | 3.6 |
| q_0168 | long-tail |  | eval_queries.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.5 | 4.3 |
| q_0169 | long-tail |  | eval_queries.jsonl | SMPVT001-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.8 | 3.5 |
| q_0170 | long-tail |  | eval_queries.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.69 | 1.00 | 0.00 | 0.00 | 4.0 | 4.4 |
| q_0171 | long-tail |  | eval_queries.jsonl | SOPQA004-3-00 | 0.00 | 0.00 | 1.00 | 0.79 | 0.00 | 0.00 | 3.8 | 3.2 |
| q_0172 | long-tail |  | eval_queries.jsonl | SOPQA008-3-02生产过程质量监控标准操作规程 | 0.00 | 0.00 | 0.48 | 1.00 | 0.00 | 0.00 | 4.4 | 3.1 |
| q_0173 | long-tail |  | eval_queries.jsonl | SOPQA010-3-00 | 0.00 | 0.00 | 1.00 | 0.95 | 0.00 | 0.00 | 4.1 | 3.7 |
| q_0174 | long-tail |  | eval_queries.jsonl | SOPQC-CP018-3-01 | 0.00 | 0.00 | 0.97 | 0.90 | 0.00 | 0.00 | 7.0 | 3.6 |
| q_0175 | long-tail |  | eval_queries.jsonl | SOPQC-CP028-3-02 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.1 | 3.6 |
| q_0176 | long-tail |  | eval_queries.jsonl | SOPQC-FL007-3-03 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.0 | 3.9 |
| q_0177 | long-tail |  | eval_queries.jsonl | SOPQC-FL017-3-02 | 0.00 | 0.00 | 0.00 | 0.32 | 0.00 | 0.00 | 4.1 | 3.7 |
| q_0178 | long-tail |  | eval_queries.jsonl | SOPQC-FL045-3-01 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.7 | 3.5 |
| q_0179 | long-tail |  | eval_queries.jsonl | SOPQC-TZ049-3-00 | 0.00 | 0.00 | 1.00 | 0.85 | 0.00 | 0.00 | 4.6 | 3.9 |
| q_0180 | long-tail |  | eval_queries.jsonl | SOPQC-TZ054-3-01 | 0.00 | 0.00 | 0.88 | 1.00 | 0.00 | 0.00 | 3.7 | 3.2 |
| q_0181 | multi-hop |  | eval_queries.jsonl | SOPQA010-3-00 | 0.00 | 0.00 | 0.83 | 0.51 | 0.00 | 0.00 | 3.4 | 3.1 |
| q_0182 | multi-hop |  | eval_queries.jsonl | SOPQC-YL012-3-01 | 0.00 | 0.00 | 0.60 | 0.58 | 0.00 | 0.00 | 4.2 | 3.8 |
| q_0183 | multi-hop |  | eval_queries.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 1.00 | 0.98 | 0.00 | 0.00 | 6.4 | 4.2 |
| q_0184 | multi-hop |  | eval_queries.jsonl | SOPQA004-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.1 | 3.5 |
| q_0185 | multi-hop |  | eval_queries.jsonl | SMPVT001-3-00 | 0.00 | 0.00 | 0.90 | 0.54 | 0.00 | 0.00 | 5.5 | 3.3 |
| q_0186 | multi-hop |  | eval_queries.jsonl | SMPVT001-3-00 | 0.00 | 0.00 | 0.90 | 0.54 | 0.00 | 0.00 | 4.0 | 3.4 |
| q_0187 | multi-hop |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 0.98 | 0.73 | 0.00 | 0.00 | 4.1 | 3.3 |
| q_0188 | multi-hop |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 1.00 | 0.69 | 0.00 | 0.00 | 4.0 | 3.3 |
| q_0189 | multi-hop |  | eval_queries.jsonl | SOPQC-TZ049-3-00 | 0.00 | 0.00 | 1.00 | 0.92 | 0.00 | 0.00 | 3.9 | 3.8 |
| q_0190 | multi-hop |  | eval_queries.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 0.98 | 0.73 | 0.00 | 0.00 | 5.6 | 3.2 |
| q_0191 | multi-hop |  | eval_queries.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.90 | 0.85 | 0.00 | 0.00 | 3.9 | 4.4 |
| q_0192 | multi-hop |  | eval_queries.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 1.00 | 0.92 | 0.00 | 0.00 | 4.2 | 3.5 |
| q_0193 | multi-hop |  | eval_queries.jsonl | SOPQC-CP028-3-02 | 0.00 | 0.00 | 0.69 | 0.69 | 0.00 | 0.00 | 5.5 | 3.5 |
| q_0194 | multi-hop |  | eval_queries.jsonl | SOPQC-TZ063-3-00 | 0.00 | 0.00 | 0.62 | 0.64 | 0.00 | 0.00 | 5.0 | 3.8 |
| q_0195 | multi-hop |  | eval_queries.jsonl | SOPQC-FL017-3-02 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.6 | 3.4 |
| h_0001 | definitional |  | eval_queries_holdout.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.9 | 3.0 |
| h_0002 | definitional |  | eval_queries_holdout.jsonl | SMPGW043-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.4 | 3.2 |
| h_0003 | procedural |  | eval_queries_holdout.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.80 | 1.00 | 0.00 | 0.00 | 4.5 | 3.6 |
| h_0004 | procedural |  | eval_queries_holdout.jsonl | SMPGW049-3-00 | 0.00 | 0.00 | 0.80 | 1.00 | 0.00 | 0.00 | 3.7 | 3.5 |
| h_0005 | procedural |  | eval_queries_holdout.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.91 | 0.95 | 0.00 | 0.00 | 3.3 | 3.3 |
| h_0006 | procedural |  | eval_queries_holdout.jsonl | SMPQA012-3-00 | 0.00 | 0.00 | 0.91 | 0.95 | 0.00 | 0.00 | 3.5 | 3.1 |
| h_0007 | procedural |  | eval_queries_holdout.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.5 | 3.0 |
| h_0008 | factual |  | eval_queries_holdout.jsonl | SMPQC015-3-00 | 0.00 | 0.00 | 0.92 | 1.00 | 0.00 | 0.00 | 4.5 | 3.3 |
| h_0009 | numerical |  | eval_queries_holdout.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 0.97 | 0.86 | 0.00 | 0.00 | 4.4 | 3.3 |
| h_0010 | definitional |  | eval_queries_holdout.jsonl | SMPQC018-3-02 | 0.00 | 0.00 | 1.00 | 0.88 | 0.00 | 0.00 | 5.2 | 3.6 |
| h_0011 | factual |  | eval_queries_holdout.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 0.97 | 0.95 | 0.00 | 0.00 | 3.5 | 3.2 |
| h_0012 | definitional |  | eval_queries_holdout.jsonl | SMPQC020-3-00 | 0.00 | 0.00 | 0.97 | 0.94 | 0.00 | 0.00 | 3.5 | 3.2 |
| h_0013 | procedural |  | eval_queries_holdout.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.85 | 0.88 | 0.00 | 0.00 | 4.1 | 3.7 |
| h_0014 | definitional |  | eval_queries_holdout.jsonl | SMPSC008-3-01 | 0.00 | 0.00 | 0.84 | 0.71 | 0.00 | 0.00 | 3.8 | 3.2 |
| h_0015 | procedural |  | eval_queries_holdout.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 1.00 | 0.92 | 0.00 | 0.00 | 5.7 | 4.4 |
| h_0016 | numerical |  | eval_queries_holdout.jsonl | SMPSC021-3-00 | 0.00 | 0.00 | 1.00 | 0.85 | 0.00 | 0.00 | 3.8 | 3.8 |
| h_0017 | definitional |  | eval_queries_holdout.jsonl | SMPVT001-3-00 | 0.00 | 0.00 | 0.86 | 0.95 | 0.00 | 0.00 | 3.8 | 2.9 |
| h_0018 | procedural |  | eval_queries_holdout.jsonl | SMPVT001-3-00 | 0.00 | 0.00 | 0.89 | 0.97 | 0.00 | 0.00 | 3.9 | 3.2 |
| h_0019 | procedural |  | eval_queries_holdout.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.67 | 1.00 | 0.00 | 0.00 | 3.4 | 3.3 |
| h_0020 | definitional |  | eval_queries_holdout.jsonl | SOPQA002-3-00 | 0.00 | 0.00 | 0.65 | 0.92 | 0.00 | 0.00 | 6.6 | 3.3 |
| h_0021 | procedural |  | eval_queries_holdout.jsonl | SOPQA004-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.7 | 3.6 |
| h_0022 | numerical |  | eval_queries_holdout.jsonl | SOPQA004-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.7 | 3.4 |
| h_0023 | factual |  | eval_queries_holdout.jsonl | SOPQA008-3-02生产过程质量监控标准操作规程 | 0.00 | 0.00 | 0.50 | 1.00 | 0.00 | 0.00 | 4.3 | 3.1 |
| h_0024 | factual |  | eval_queries_holdout.jsonl | SOPQA008-3-02生产过程质量监控标准操作规程 | 0.00 | 0.00 | 0.50 | 1.00 | 0.00 | 0.00 | 3.5 | 2.9 |
| h_0025 | definitional |  | eval_queries_holdout.jsonl | SOPQA010-3-00 | 0.00 | 0.00 | 0.88 | 0.50 | 0.00 | 0.00 | 3.8 | 3.2 |
| h_0026 | numerical |  | eval_queries_holdout.jsonl | SOPQA010-3-00 | 0.00 | 0.00 | 0.88 | 0.50 | 0.00 | 0.00 | 3.7 | 3.5 |
| h_0027 | definitional |  | eval_queries_holdout.jsonl | SOPQC-CP018-3-01 | 0.00 | 0.00 | 0.63 | 0.58 | 0.00 | 0.00 | 3.6 | 3.9 |
| h_0028 | factual |  | eval_queries_holdout.jsonl | SOPQC-CP018-3-01 | 0.00 | 0.00 | 1.00 | 0.58 | 0.00 | 0.00 | 3.8 | 4.5 |
| h_0029 | numerical |  | eval_queries_holdout.jsonl | SOPQC-CP028-3-02 | 0.00 | 0.00 | 0.92 | 0.92 | 0.00 | 0.00 | 3.6 | 3.7 |
| h_0030 | factual |  | eval_queries_holdout.jsonl | SOPQC-CP028-3-02 | 0.00 | 0.00 | 0.69 | 0.69 | 0.00 | 0.00 | 3.7 | 3.4 |
| h_0031 | definitional |  | eval_queries_holdout.jsonl | SOPQC-FL007-3-03 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.6 | 4.0 |
| h_0032 | procedural |  | eval_queries_holdout.jsonl | SOPQC-FL007-3-03 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 6.1 | 3.7 |
| h_0033 | numerical |  | eval_queries_holdout.jsonl | SOPQC-FL017-3-02 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.3 | 3.6 |
| h_0034 | factual |  | eval_queries_holdout.jsonl | SOPQC-FL017-3-02 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.9 | 4.2 |
| h_0035 | definitional |  | eval_queries_holdout.jsonl | SOPQC-FL045-3-01 | 0.00 | 0.00 | 0.63 | 0.79 | 0.00 | 0.00 | 4.6 | 3.5 |
| h_0036 | procedural |  | eval_queries_holdout.jsonl | SOPQC-FL045-3-01 | 0.00 | 0.00 | 0.50 | 0.79 | 0.00 | 0.00 | 4.6 | 5.8 |
| h_0037 | definitional |  | eval_queries_holdout.jsonl | SOPQC-TZ049-3-00 | 0.00 | 0.00 | 1.00 | 0.85 | 0.00 | 0.00 | 3.9 | 3.5 |
| h_0038 | factual |  | eval_queries_holdout.jsonl | SOPQC-TZ049-3-00 | 0.00 | 0.00 | 1.00 | 0.92 | 0.00 | 0.00 | 3.3 | 3.3 |
| h_0039 | numerical |  | eval_queries_holdout.jsonl | SOPQC-TZ054-3-01 | 0.00 | 0.00 | 0.92 | 0.69 | 0.00 | 0.00 | 3.4 | 3.6 |
| h_0040 | procedural |  | eval_queries_holdout.jsonl | SOPQC-TZ054-3-01 | 0.00 | 0.00 | 0.82 | 0.69 | 0.00 | 0.00 | 3.6 | 3.6 |
| h_0041 | procedural |  | eval_queries_holdout.jsonl | SOPQC-TZ057-3-00 | 0.00 | 0.00 | 1.00 | 0.81 | 0.00 | 0.00 | 4.2 | 3.5 |
| h_0042 | procedural |  | eval_queries_holdout.jsonl | SOPQC-TZ057-3-00 | 0.00 | 0.00 | 1.00 | 0.81 | 0.00 | 0.00 | 5.2 | 3.9 |
| h_0043 | definitional |  | eval_queries_holdout.jsonl | SOPQC-TZ063-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.3 | 4.1 |
| h_0044 | procedural |  | eval_queries_holdout.jsonl | SOPQC-TZ063-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.5 | 3.6 |
| h_0045 | procedural |  | eval_queries_holdout.jsonl | SOPQC-YL007-3-00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.5 | 3.5 |
| h_0046 | factual |  | eval_queries_holdout.jsonl | SOPQC-YL007-3-00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 3.4 |
| h_0047 | factual |  | eval_queries_holdout.jsonl | SOPQC-YL012-3-01 | 0.00 | 0.00 | 0.59 | 0.56 | 0.00 | 0.00 | 3.5 | 3.3 |
| h_0048 | factual |  | eval_queries_holdout.jsonl | SOPQC-YL012-3-01 | 0.00 | 0.00 | 0.59 | 0.56 | 0.00 | 0.00 | 4.1 | 3.3 |
| h_0049 | procedural |  | eval_queries_holdout.jsonl | SOPQC-YQ017-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.7 | 3.8 |
| h_0050 | definitional |  | eval_queries_holdout.jsonl | SOPQC-YQ017-3-00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.8 | 3.7 |
| neg_0001 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.9 | 3.6 |
| neg_0002 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.9 | 3.3 |
| neg_0003 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.0 | 3.2 |
| neg_0004 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.5 | 3.3 |
| neg_0005 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.5 | 3.5 |
| neg_0006 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 7.0 | 3.4 |
| neg_0007 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.8 | 3.3 |
| neg_0008 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.6 | 3.4 |
| neg_0009 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.7 | 3.2 |
| neg_0010 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 3.3 |
| neg_0011 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.4 | 3.1 |
| neg_0012 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.7 | 3.6 |
| neg_0013 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.8 | 3.1 |
| neg_0014 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.4 | 3.3 |
| neg_0015 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.7 | 3.5 |
| neg_0016 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.2 | 3.3 |
| neg_0017 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.3 | 3.4 |
| neg_0018 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 4.2 |
| neg_0019 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.9 | 3.2 |
| neg_0020 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.1 | 3.2 |
| neg_0021 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.0 | 3.1 |
| neg_0022 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.3 | 3.9 |
| neg_0023 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 3.4 |
| neg_0024 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.7 | 3.3 |
| neg_0025 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.5 | 3.5 |
| neg_0026 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.2 | 3.3 |
| neg_0027 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 5.6 | 3.2 |
| neg_0028 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 3.0 |
| neg_0029 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.0 | 3.2 |
| neg_0030 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.4 | 3.3 |
| neg_0031 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.6 | 3.4 |
| neg_0032 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 4.3 | 3.3 |
| neg_0033 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.7 | 3.5 |
| neg_0034 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 4.0 |
| neg_0035 | negative | ✓ | negative_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.9 | 3.4 |
| adv_0001 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.73 | 0.51 | 0.00 | 0.00 | 3.7 | 3.4 |
| adv_0002 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.5 | 3.5 |
| adv_0003 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.95 | 0.99 | 0.00 | 0.00 | 4.2 | 3.7 |
| adv_0004 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.98 | 1.00 | 0.00 | 0.00 | 3.8 | 3.3 |
| adv_0005 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.50 | 0.93 | 0.00 | 0.00 | 4.9 | 3.1 |
| adv_0006 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.0 | 3.1 |
| adv_0007 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 0.69 | 0.00 | 0.00 | 5.2 | 3.4 |
| adv_0008 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.8 | 3.8 |
| adv_0009 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.6 | 4.2 |
| adv_0010 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.8 | 3.4 |
| adv_0011 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.7 | 3.7 |
| adv_0012 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3.7 | 3.1 |
| adv_0013 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 0.69 | 0.00 | 0.00 | 3.5 | 3.5 |
| adv_0014 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.94 | 0.99 | 0.00 | 0.00 | 3.7 | 3.8 |
| adv_0015 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.92 | 0.96 | 0.00 | 0.00 | 5.8 | 4.0 |
| adv_0016 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.99 | 0.95 | 0.00 | 0.00 | 5.9 | 3.7 |
| adv_0017 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.97 | 0.91 | 0.00 | 0.00 | 6.6 | 3.3 |
| adv_0018 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 5.5 | 4.9 |
| adv_0019 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 4.9 | 3.2 |
| adv_0020 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.94 | 0.96 | 0.00 | 0.00 | 7.1 | 3.1 |
| adv_0021 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.4 | 3.2 |
| adv_0022 | adversarial |  | adversarial_queries.jsonl | — | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 3.8 | 3.6 |
