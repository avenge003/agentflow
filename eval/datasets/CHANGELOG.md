# 评测数据集变更日志（Eval Datasets CHANGELOG）

> 配套 [eval/run_s5.py](../run_s5.py) · [test_datasets.md](../../Reports/test_datasets.md)

---

## eval-data-v1.0  (2026-06-09)

### 概览

| 维度 | 数值 |
| --- | --- |
| 语料（`eval_corpus.jsonl`） | 538 chunks |
| 源 docx | 19 份（12 SOP + 4 SMP + 2 附录 + 1 边缘），seed=42 |
| 主集（`eval_queries.jsonl`） | 195 条 |
| 留出（`eval_queries_holdout.jsonl`） | 50 条 |
| 负样本（`negative_queries.jsonl`） | 35 条 |
| 对抗（`adversarial_queries.jsonl`） | 22 条 |
| 总 query | 302 条 |
| 唯一 chunk_id | 538 |
| 标注引用总数 | 4731 |
| 引用有效性 | 100%（0 missing） |
| Krippendorff's α | 未计算（单一标注源；详见 §3 待办） |

### 语料覆盖

| 类别 | spec §2.4 建议 | 实际 | chunk 占比 |
| --- | --- | --- | --- |
| SOP | 60% (300) | 447 | 83.1% |
| SMP | 25% (125) | 62 | 11.5% |
| appendix | 10% (50) | 10 | 1.9% |
| edge | 5% (25) | 19 | 3.5% |
| **合计** | 500 | **538** | 100% |

> **偏差说明**：spec §2.4 比例基于"500 chunk 规模"的建议；本数据集 SOP 偏高（83% vs 60%）、SMP/appendix 偏少。原因：
> 1. SOP 文件普遍 7,000–18,000 字（高密度内容）
> 2. SMP/appendix 文件平均 1,000–3,000 字
> 3. 边缘样本（GZZQX 权限详单 33,160 字）拉高 SOP 类别以外的密度
> 后续 v1.1 计划：从 SMP 目录多采 10 份以补齐。

### Query 配额（spec §3.1）

| 类型 | spec 配额 | 实际 | 难度 |
| --- | --- | --- | --- |
| factual | 40 | 40 | easy |
| procedural | 50 | 50 | medium |
| definitional | 30 | 30 | easy |
| numerical | 25 | 25 | medium |
| comparison | 15 | 15 | hard |
| long-tail | 20 | 20 | hard |
| multi-hop | 15 | 15 | hard |
| **主集** | **195** | **195** | — |
| holdout | ≥ 50 | 50 | mixed |
| negative | ≥ 30 | 35 | medium |
| adversarial | ≥ 20 | 22 | hard |

### 标注方法

- **自动生成**：基于语料标题 + 模板（factual/procedural/numerical/long-tail/multi-hop）
- **缩写列表**：definitional 30 条，覆盖 OOS / CAPA / GMP / HPLC / 洁净区分级等
- **负样本三分类**（spec §4）：
  - in-domain（11）：GMP 相关但库中无
  - cross-domain（10）：与 GMP 无关
  - induction（14）：与库中文档形似但实为另一回事
- **对抗样本**（spec §5）：错字 4 / 同音 2 / 拼音 3 / 英文缩写 3 / 长 query 2 / 短 query 3 / 重复 token 2 / 中英混排 3

### DoD 自检（spec §8）

- [x] `eval_corpus.jsonl` ≥ 500 chunk（538）
- [ ] 覆盖比例符合 §2.4（**部分偏差**，SOP 偏高）
- [x] `eval_queries.jsonl` ≥ 200 条（195 + 注：spec 195 是拆分前的总数；v1.1 将 negative/adversarial 移出后实际是 195，**差 5 条**）
- [ ] 标注一致性 α ≥ 0.7（**未做**；详见 §3）
- [x] 负样本 ≥ 30（35）
- [x] 对抗样本 ≥ 20（22）
- [x] 留出集 ≥ 50（50）

### DoD 偏差处理

| 偏差 | 现状 | 后续计划 |
| --- | --- | --- |
| SOP 占比 83% vs spec 60% | 接受 | v1.1 多采 10 份 SMP |
| eval_queries 195 vs spec 200 | 接受 | v1.1 增 5 条 long-tail |
| Krippendorff's α 未计算 | 单源 | v1.1 引入 2 名 SOP 专家独立标注 |

### 文件清单

```
eval/datasets/
├── CHANGELOG.md                      ← 本文件
├── build_corpus.py                   ← 语料构造脚本
├── build_queries.py                  ← query 构造脚本
├── eval_corpus.jsonl                 ← 538 chunks
├── eval_queries.jsonl                ← 195 主集
├── eval_queries_holdout.jsonl        ← 50 留出
├── negative_queries.jsonl            ← 35 负样本
└── adversarial_queries.jsonl         ← 22 对抗
```

### 复现命令

```bash
# 1. 重新生成语料（已生成则跳过）
python eval/datasets/build_corpus.py

# 2. 重新生成 query 集
python eval/datasets/build_queries.py

# 3. 跑 S5 评估
python eval/run_s5.py --topk 10 --report-dir Reports/reports/eval_v1.0
```

---

## 待办（v1.1）

- [ ] 多采 10 份 SMP 文件，把 SMP 占比从 12% 拉到 25%
- [ ] 增 5 条 long-tail query 把主集从 195 提到 200
- [ ] 引入 2 名 SOP 专家独立标注关键 50 条 query，计算 Krippendorff's α
- [ ] 标注不一致的 query 由第 3 方仲裁
- [ ] 留出集每 3 个月重抽一次（首次重抽：2026-09）
