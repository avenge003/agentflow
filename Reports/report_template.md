# 评估报告模板（Report Template）

> 配套文档：[evaluation_plan.md](evaluation_plan.md)
> 每次评估**必须**按本模板渲染输出 `Reports/reports/eval_<ts>/report.md`，便于版本化比对。

---

## 1. 文件结构

```
Reports/reports/eval_20260609_120000_a1b2c3d/
├── report.md            # 本模板渲染
├── metrics.json         # 原始指标（机器可读）
├── config_snapshot.yaml # 当时服务 / 模型 / Milvus 配置
├── latency_distribution.png
├── resource_usage.png
└── raw_responses.jsonl  # 每个 query 的原始返回（不入 git）
```

---

## 2. report.md 模板

```markdown
# 评估报告 — eval_<RUN_ID>

| 字段 | 值 |
| --- | --- |
| 运行时间 | <YYYY-MM-DD HH:MM:SS> |
| 触发人 / CI | <author> |
| App 版本 | <app_version> |
| 评估方案版本 | v1.0.0 |
| 测试集版本 | eval_queries_v1.0 |
| 数据规模 | queries=N, corpus=M |
| Embedding | <model> |
| Reranker | <model> |
| Milvus | <version>, collection=<name> |
| 总结论 | ✅ Pass / 🟡 Warn / 🔴 Fail |

---

## 1. TL;DR

- 关键变化（与 baseline 比）：
  - NDCG@10: <Δ>（<方向> <幅度>）
  - p95 延迟: <Δ>
  - 5xx 率: <Δ>
- 风险 / 阻塞：<list>

## 2. L0 · 安全 & 治理

| 指标 | 当前 | 阈值 | 结论 |
| --- | --- | --- | --- |
| auth.pass_rate (合法) |  | 1.00 |  |
| auth.pass_rate (非法) |  | 0.00 |  |
| authz.tenant_isolation |  | 0 泄漏 |  |
| input.safety (5xx) |  | 0 |  |
| pii.leakage |  | 0 |  |

## 3. L1 · 系统 & 接口

| 指标 | 当前 | 上版 | Δ | 阈值 | 结论 |
| --- | --- | --- | --- | --- | --- |
| perf.latency_p50 (ms) |  |  |  | ≤400 |  |
| perf.latency_p95 (ms) |  |  |  | ≤800 |  |
| perf.latency_p99 (ms) |  |  |  | ≤1500 |  |
| perf.qps |  |  |  | ≥10 |  |
| perf.cold_start (s) |  |  |  | ≤30 |  |
| rel.error_rate (5xx) |  |  |  | <0.1% |  |
| api.dify_compliance |  |  |  | 100% |  |

## 4. L2 · 数据 & 索引

| 指标 | 当前 | 阈值 | 结论 |
| --- | --- | --- | --- |
| data.chunk_size_dist (p50) |  | 200–500 |  |
| data.dedup_rate |  | <1% |  |
| data.subject_coverage |  | ≥95% |  |
| data.milvus_schema_consistency |  | 100% |  |

## 5. L3 · 检索 + 重排

| 指标 | 当前 | 上版 | Δ | 阈值 | 结论 |
| --- | --- | --- | --- | --- | --- |
| Recall@1 |  |  |  | — |  |
| Recall@5 |  |  |  | — |  |
| Recall@10 |  |  |  | ≥0.85 |  |
| Precision@10 |  |  |  | ≥0.60 |  |
| MRR |  |  |  | ≥0.70 |  |
| NDCG@10 |  |  |  | ≥0.80 |  |
| MAP@10 |  |  |  | ≥0.75 |  |
| Hit Rate@10 |  |  |  | ≥0.95 |  |
| rerank.ndcg_gain |  |  |  | ≥+0.05 |  |

## 6. L4 · 端到端（如有）

| 指标 | 当前 | 阈值 | 结论 |
| --- | --- | --- | --- |
| Context Precision |  | ≥0.80 |  |
| Context Recall |  | ≥0.85 |  |
| Faithfulness (Proxy) |  | ≥0.75 |  |
| Hallucination Risk |  | <0.20 |  |
| Refusal Accuracy |  | ≥0.80 |  |

## 7. 消融结果

| 编号 | 配置 | NDCG@10 | p95(ms) | 备注 |
| --- | --- | --- | --- | --- |
| A1 | 向量 |  |  |  |
| A2 | 向量 + reranker |  |  | 当前 |
| A3 | 向量 + reranker + 阈值 |  |  |  |
| A4 | reranker only |  |  |  |
| A5 | 真实 BM25 + 向量 |  |  |  |
| A6 | 纯 BM25 |  |  |  |

## 8. 失败用例 Top10

| query | 类型 | 期望 chunk | 实际 top-3 | 失败原因 |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## 9. 图表

- 延迟分布：![](latency_distribution.png)
- 资源占用：![](resource_usage.png)
- (可选) NDCG 类别细分柱状图

## 10. 结论与建议

- [ ] 通过：<指标>
- [ ] 警告：<指标>，原因 / 处置建议
- [ ] 失败：<指标>，阻塞发版

## 11. 附件

- `metrics.json`
- `config_snapshot.yaml`
- 失败用例详情（JSONL）
- (可选) 完整压测报告 `locust.html`
```

---

## 3. config_snapshot.yaml 模板

```yaml
run_id: eval_20260609_120000_a1b2c3d
timestamp: "2026-06-09T12:00:00+08:00"

app:
  version: 1.0.0
  commit: <git rev-parse HEAD>
  config: app/core/config.py

milvus:
  host: localhost
  port: 19530
  version: 2.4.x
  collection: eval_<uuid>
  num_entities: 1234
  indexes:
    vector: { type: IVF_FLAT, nlist: 1024, metric: IP }

models:
  embedding:
    path: ./models/embedding/bge-large-zh-v1.5
    dim: 1024
    device: cuda
    fp16: true
  reranker:
    path: ./models/reranker/bge-reranker-large
    max_length: 512
    device: cuda
    fp16: true

retrieval:
  top_k: 10
  score_threshold: 0.0
  bm25_weight: 0.5
  vector_weight: 0.5

hardware:
  cpu: 8 cores
  ram_gb: 32
  gpu: NVIDIA A10 (24GB)
```

---

## 4. 渲染脚本（占位）

```python
# tools/report_renderer.py
import json, jinja2, datetime
from pathlib import Path

def render(metrics: dict, baseline: dict | None, output_dir: Path):
    tpl = jinja2.Template(Path("Reports/report_template.md").read_text())
    md = tpl.render(
        run_id=metrics["version"],
        timestamp=metrics["timestamp"],
        app_version=metrics["app_version"],
        metrics=metrics["metrics"],
        delta=_compute_delta(metrics["metrics"], baseline) if baseline else {},
    )
    (output_dir / "report.md").write_text(md)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
```

---

## 5. 发布门禁（Release Gate）

评估报告 `Conclusion = ✅ Pass` 才允许合并到 `main`。`🟡 Warn` 需负责人 approve，`🔴 Fail` 自动 block PR。
