# 基准测试场景（Benchmark Scenarios）

> 配套文档：[evaluation_plan.md](evaluation_plan.md) · [metrics_reference.md](metrics_reference.md) · [test_datasets.md](test_datasets.md)
> 目标：定义**可复现**的压测 / 评测场景，给出"什么场景、用什么数据、跑什么指标"。

---

## 1. 场景总览

| 编号 | 场景 | 主要评估维度 | 频率 |
| --- | --- | --- | --- |
| S1 | 冷启动 | L1 `perf.cold_start` | 每次发版 |
| S2 | 单请求基准 | L1 `perf.latency_p*` | 每次发版 |
| S3 | 持续高并发 | L1 `perf.qps` / `perf.resource` / `rel.error_rate` | 每次发版 |
| S4 | 混合负载（写 + 读） | L1 + L2 | 每次发版 |
| S5 | 检索质量回归 | L3 | 每次发版 + 模型变更 |
| S6 | 重排消融 | L3 `rerank.*` | 算法变更 |
| S7 | 阈值与权重扫描 | L3 | 每次发版 |
| S8 | 故障注入 | L1 `rel.recovery` | 每月 |
| S9 | 协议契约 | L0 / L1 `api.*` | 每次发版 |
| S10 | 安全 Fuzz | L0 | 每次发版 |
| S11 | 端到端问答 | L4 | 大版本 |

---

## 2. 通用配置

```yaml
# eval/scenarios/config.yaml
service:
  base_url: http://localhost:8002
  api_key: ${RAGFLOW_API_KEY}
  timeout_s: 30
  headers:
    Authorization: "Bearer ${api_key}"
    Content-Type: "application/json"
retrieval:
  default_top_k: 10
  default_score_threshold: 0.0
milvus:
  host: localhost
  port: 19530
  collection: eval_<run_id>
```

---

## 3. S1 · 冷启动

### 目的

验证从"完全无进程"到"首条 200"的端到端时间。

### 步骤

1. `pkill -f uvicorn`
2. `ps -ef | grep uvicorn | grep -v grep` 确认无进程
3. 记录 `t0`
4. `bash run.sh &`
5. 启动 1 个并发用户，每秒 1 个 `/health` 请求探测
6. 首次返回 200 时记录 `t1`
7. `cold_start = t1 - t0`

### 判定

| 等级 | 阈值 |
| --- | --- |
| ✅ | ≤ 30s |
| 🟡 | 30s – 60s |
| 🔴 | > 60s |

---

## 4. S2 · 单请求基准

### 步骤

```python
import time, requests
from eval.datasets.eval_queries import load_queries

queries = load_queries("eval_queries.jsonl")  # 200 条
latencies = []
for q in queries:
    payload = {
        "knowledge_id": "eval_kb",
        "query": q["query"],
        "retrieval_setting": {"top_k": 10, "score_threshold": 0.0},
    }
    t0 = time.perf_counter()
    r = requests.post("http://localhost:8002/retrieval",
                      json=payload, timeout=30)
    latencies.append((time.perf_counter() - t0) * 1000)
    r.raise_for_status()
```

### 指标

- p50 / p95 / p99
- 错误率
- 与上版本差值

---

## 5. S3 · 持续高并发

### locustfile.py

```python
from locust import HttpUser, task, between
import random, json

class RetrievalUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def retrieval(self):
        payload = {
            "knowledge_id": "eval_kb",
            "query": random.choice(QUERIES),
            "retrieval_setting": {"top_k": 10, "score_threshold": 0.0},
        }
        with self.client.post("/retrieval", json=payload, catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"status={r.status_code}")
            elif len(r.json().get("records", [])) == 0:
                r.failure("empty records")
```

### 矩阵

| 用户数 | 持续时间 | 评估目标 |
| --- | --- | --- |
| 10 | 5 min | 基线吞吐 |
| 50 | 5 min | 压测 p95 |
| 100 | 3 min | 极限测试（错误率不超 1%） |

### 同步采样

```bash
nvidia-smi dmon -s pucm -d 1 -f gpu.log &
psutil-cpu sampler  # 自研 1s 采样
locust -f locustfile.py -u 50 -r 10 -t 5m --headless --html locust.html
```

---

## 6. S4 · 混合负载（写 + 读）

### 配比

- 80% 读（`/retrieval`）
- 15% 写（`/documents/store`，单批 1–10 chunk）
- 4% 更新（`/documents/update`）
- 1% 删除（`/documents/delete`）

### 评估

- 读写成功率分别统计
- 写后立即读的一致性：刚写的 chunk_id 在 1s 内能否被检索到
- **重点验证 G3（update 非原子）**：并发 update 同一 title 是否有数据丢失

---

## 7. S5 · 检索质量回归

### 步骤

1. 用 `eval_corpus.jsonl` 灌库
2. 跑 `eval_queries.jsonl` 全部 query
3. 计算 Recall@K / Precision@K / MRR / NDCG@K / Hit Rate@K
4. 与上一 baseline 对比

### 报告

```markdown
| 指标 | 当前 | 上版 | Δ | 结论 |
| --- | --- | --- | --- | --- |
| Recall@10 | 0.87 | 0.85 | +0.02 | ✅ |
| NDCG@10  | 0.81 | 0.83 | -0.02 | 🟡 |
| MRR      | 0.74 | 0.74 | 0.00 | ✅ |
```

### 判定

- 主指标（Recall@10、NDCG@10）任一下降 ≥ 0.05 → 🔴
- 下降 < 0.05 → 🟡
- 持平或上升 → ✅

---

## 8. S6 · 重排消融

| 配置 | 描述 | 文件 / 参数 |
| --- | --- | --- |
| Base | 仅向量检索（关 rerank） | `score_threshold=0.0` + 跳过 `rerank()` |
| A2 | 向量 + reranker（当前） | 保持现状 |
| A3 | 向量 + reranker + 阈值 | 设 `score_threshold=0.5` |
| A4 | reranker only | 用候选 50 → rerank top10 |

代码改造点（仅评估时用，**不**合入主分支）：

```python
# eval/harness.py
def retrieval_v2(query, mode):
    if mode == "no_rerank":
        # 直接用 Milvus 排序
        ...
    elif mode == "rerank_only":
        # 拿 50 候选 → rerank 取 top10
        ...
    else:  # default
        ...
```

### 报告

- `rerank.ndcg_gain`
- `rerank.top1_swap_rate`
- `rerank.score_calibration`

---

## 9. S7 · 阈值与权重扫描

| 参数 | 扫描范围 | 步长 |
| --- | --- | --- |
| `score_threshold` | 0.0, 0.2, 0.4, 0.6, 0.8 | 0.2 |
| `top_k` | 5, 10, 20, 50 | — |
| `bm25_weight` | 0.0, 0.3, 0.5, 0.7, 1.0 | 0.2 |
| `vector_weight` | `1 - bm25_weight` | — |

> **注意**：当前实现 (G1) `bm25_weight` 未真正生效，扫描时需切换到"真实融合"实现：
>
> ```python
> # 仅评估用
> hybrid_results = milvus_service.hybrid_search(
>     dense_vec=vec, sparse_vec=bm25_vec,
>     top_k=50, weight=(0.5, 0.5),
> )
> ```

### 输出

绘制 Recall@10、p95 latency 关于 (bm25_weight, score_threshold) 的热力图。

---

## 10. S8 · 故障注入

| 故障 | 注入方式 | 期望行为 |
| --- | --- | --- |
| Milvus 断开 | `docker stop milvus-standalone` | API 返回 5xx，重启后自动恢复 ≤ 10s |
| 集合不存在 | drop collection | 返回 200 + 空 records，**不** 5xx |
| Embedding 模型加载失败 | 改 `embedding_model_path` 为非法 | 启动失败日志明确 |
| Reranker 模型加载失败 | 同上 | 同上 |
| 显存耗尽 | 同时跑多 worker | 启动排队或降级（需人工评估） |

### 工具

- 简单：`docker stop / start`
- 高级：`chaos-mesh` / `chaosblade`

---

## 11. S9 · 协议契约

```python
import schemathesis
from app.main import app

schema = schemathesis.from_asgi("/openapi.json", app)
@schema.parametrize()
def test_api(case):
    case.call_and_validate()
```

### 用例覆盖

| 类别 | 样例 |
| --- | --- |
| 必填缺失 | 缺 `knowledge_id` / `query` |
| 类型错误 | `top_k="abc"` |
| 范围越界 | `score_threshold=2.0` |
| 鉴权 | 见 L0 用例 |
| 错误码 | 1001 / 1002 / 2001 |

---

## 12. S10 · 安全 Fuzz

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=0, max_size=10_000))
def test_query_fuzz(q):
    r = client.post("/retrieval", json={
        "knowledge_id": "k1",
        "query": q,
        "retrieval_setting": {"top_k": 3, "score_threshold": 0.0},
    })
    assert r.status_code < 500, f"5xx for query={q!r}"
```

覆盖：
- 极长 query
- 特殊字符（`\x00`、`\r\n`、`"`）
- Markdown / HTML 注入
- `score_threshold: -1` / `top_k: -1`

---

## 13. S11 · 端到端问答

### 流程

1. query 检索 top-10
2. 拼成 prompt：`context: <top-10> \n question: <query>`
3. 调用 LLM（本评估用 `Qwen2.5-7B-Instruct` 或 `gpt-4o-mini`）
4. 拿 LLM 答案 vs gold answer 比对

### 指标

- Faithfulness（NLI）
- Answer Relevancy
- 关键实体覆盖（NER + match）
- 人工抽检 20 条

---

## 14. 场景矩阵（DoR / DoD）

| 场景 | DoR（开始前） | DoD（结束后） |
| --- | --- | --- |
| S1 | 服务未启动 | 输出 cold_start 时间 |
| S2 | 预热 10 次 | 输出 p50/p95/p99 |
| S3 | locust 就绪 | 输出 QPS / 资源图 / 错误率 |
| S4 | corpus 灌完 | 输出读写成功率 |
| S5 | corpus + gold 就绪 | 输出指标 + 与基线 diff |
| S6 | 消融实现就绪 | 输出 4 配置对比表 |
| S7 | 真实融合实现就绪 | 输出热力图 |
| S8 | 混沌工具就绪 | 输出恢复时间 |
| S9 | OpenAPI schema 就绪 | 输出 0 failed |
| S10 | hypothesis 用例就绪 | 输出 crash 数 = 0 |
| S11 | LLM 接入 | 输出端到端报告 |
