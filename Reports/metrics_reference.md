# 指标参考手册（Metrics Reference）

> 配套文档：[evaluation_plan.md](evaluation_plan.md)
> 本文件给出每个指标的**精确定义、计算公式、测量方法、判定阈值、参考实现**。

---

## 1. 命名约定

- 指标统一 `domain.metric_name` 形式
- 单位：秒(s)、毫秒(ms)、百分比(%)、比值(0–1) 在文档中显式标注
- 所有 [0,1] 区间的指标默认 4 位小数（`0.0000`），其他用 SI 单位

---

## 2. L0 安全 & 治理

### 2.1 `auth.pass_rate`

- **定义**：鉴权用例通过率
- **方法**：构造 4 组用例，每组 100 条
  - 合法 Key：期望 200
  - 缺失 Authorization：期望 401 + `error_code=1001`
  - 非法格式（如 `Token xxx`）：期望 401 + `error_code=1001`
  - 错误 Key：期望 403 + `error_code=1002`
- **公式**：`pass_rate = pass / total`
- **阈值**：合法 1.00，非法 0.00（即"非法 100% 被拒"）

### 2.2 `authz.tenant_isolation`

- **定义**：不同 `knowledge_id` 下的数据不串
- **方法**：
  1. 用 `K_A` 写入 10 条带 `subject=A` 的 chunk
  2. 用 `K_B` 写入 10 条带 `subject=B` 的 chunk
  3. 多次以 `query="*A*"` 调用 `/retrieval`，检查 top-K 中**不出现** B 的 chunk
- **阈值**：泄漏数 = 0

### 2.3 `input.safety`

- **方法**：Fuzzing
  - 极长 query（1MB）
  - 畸形 JSON（缺括号、`{...}`)
  - 注入：query 含 `"score_threshold": 0`、布尔炸弹 `{"top_k": -1}`
  - 路径穿越：`file_path="../../../etc/passwd"`
- **判定**：不返回 5xx；pydantic 校验失败 4xx

### 2.4 `pii.leakage`

- **字典**：身份证、手机号、银行卡
- **方法**：随机抽 1000 条返回 `content`，正则匹配
- **阈值**：按企业合规要求（一般 0）

---

## 3. L1 系统 & 接口质量

### 3.1 `perf.latency_p{50,p95,p99}`

- **端到端耗时**（客户端发包 → 收到完整响应）
- **测量**：并发 1 用户，跑 200 次（去掉前 10 预热）
- **计算**：
  ```python
  import numpy as np
  p = {q: np.percentile(latencies, q) for q in (50, 95, 99)}
  ```
- **阈值（top_k=10，候选 50）**：
  - p50 ≤ 400ms
  - p95 ≤ 800ms
  - p99 ≤ 1500ms

### 3.2 `perf.cold_start`

- **方法**：
  1. `ps -ef | grep uvicorn` 确认无进程
  2. `bash run.sh &` 启动
  3. 持续发 1 req/s，直到首次 200
  4. `t_cold = t_first_200 - t_start`
- **阈值**：≤ 30s（首加载 embedding + reranker + 集合）

### 3.3 `perf.qps`

- **方法**：`locust -u 50 -r 10 -t 5m --host http://localhost:8002`
- **判定**：在 p95 不超过阈值的最大稳定 QPS
- **阈值**：≥ 10 QPS（top_k=10，1 worker，CPU 4c/GPU 1）

### 3.4 `perf.embedding_throughput`

```python
from app.services.model_service import ModelService
import time
m = ModelService(); m.load_models()
texts = ["这是一段测试文本" * 50] * 1000
t0 = time.perf_counter()
m.encode_texts(texts)
dt = time.perf_counter() - t0
print(f"throughput = {len(texts)/dt:.1f} texts/s")
```

- **阈值**：GPU fp16 ≥ 200 texts/s；CPU ≥ 30 texts/s

### 3.5 `perf.rerank_latency`

- 取 50 段约 200 字的文档，rerank 100 次
- 阈值：p95 ≤ 300ms

### 3.6 `perf.resource`

- 跑压测时同步采样
  - GPU：`nvidia-smi dmon -s pucm -d 1`
  - 内存：`psutil.virtual_memory().percent`
  - CPU：`psutil.cpu_percent(interval=1)`
- **阈值**：
  - 显存 ≤ 6GB
  - 内存 ≤ 8GB
  - CPU 平均 ≤ 70%

### 3.7 `rel.error_rate`

```python
total = sum(1 for r in responses)
err5xx = sum(1 for r in responses if r.status_code >= 500)
err4xx = sum(1 for r in responses if 400 <= r.status_code < 500)
return {"5xx_rate": err5xx/total, "4xx_rate": err4xx/total}
```

- **阈值**：5xx < 0.1%，4xx 比例应与用例分布一致

### 3.8 `rel.recovery`

- 主动 `docker restart milvus`，记录从连接断开到再次 200 的时间
- **阈值**：≤ 10s

### 3.9 `api.dify_compliance`

- 用 `schemathesis` 对 OpenAPI 跑契约测试
- 用例覆盖：
  - 必填字段缺失
  - 类型错误（`top_k="abc"`）
  - 错误码 1001/1002/2001
  - `metadata` 不为 `null`
- **阈值**：100% 通过

---

## 4. L2 数据 & 索引质量

### 4.1 `data.chunk_size_dist`

```python
sizes = [len(c["content"]) for c in chunks]
print({"p50": np.percentile(sizes, 50),
       "p95": np.percentile(sizes, 95),
       "max": max(sizes)})
```

- **建议阈值**：
  - p50 ∈ [200, 500]
  - p95 ≤ 1200
  - max ≤ 2000

### 4.2 `data.chunk_overlap`

- 对有序 chunks，统计相邻块最长公共子串 / 较短块长度
- **建议**：10%–20%

### 4.3 `data.dedup_rate`

- 用 `MinHash` (LSH, threshold 0.9) 估重
- **建议**：< 1%

### 4.4 `data.subject_coverage`

```sql
SELECT
  1 - SUM(CASE WHEN subject IS NULL OR subject = '' THEN 1 ELSE 0 END) / COUNT(*) AS coverage
FROM policy_documents;
```

- **建议**：≥ 95%

### 4.5 `data.embedding_consistency`

- 同一文本 encode 两次，cosine similarity
- **阈值**：≥ 0.9999

### 4.6 `data.milvus_schema_consistency`

- 期望 schema（与代码注释一致）：

| 字段 | dtype | dim/length | 备注 |
| --- | --- | --- | --- |
| `id` | INT64 | auto | primary key |
| `title` | VARCHAR | 256 | chunk 标识 |
| `text` | VARCHAR | 65535 | 实际 content |
| `sparse_bm25` | SPARSE_FLOAT_VECTOR | — | BM25 索引自动 |
| `vector` | FLOAT_VECTOR | 1024 | dense |
| `subject` | VARCHAR | 256 | 元数据 |

- 索引：`vector` 应有 `IVF_FLAT` 或 `HNSW`，metric = `IP`
- **判定**：完全匹配

### 4.7 `data.backup_restore`

- `milvus_backup` 创建备份 → 新集合恢复 → 抽样 1% 内容比对
- **阈值**：100% 一致

---

## 5. L3 检索 + 重排质量

### 5.1 通用前置

设：
- `Q = {q_1, ..., q_n}`：query 集合
- `G_i = {g_1, ..., g_m}`：第 i 个 query 的 gold chunk id 集合（含相关性等级 `rel ∈ {1,2,3}`）
- `R_i = [(chunk_id, score), ...]`：返回的前 K 条

### 5.2 `Recall@K`

$$
\text{Recall@K}(q_i) = \frac{| \{r \in R_i[:K] \mid r \in G_i\} |}{|G_i|}
$$

```python
def recall_at_k(retrieved, gold, k):
    return len(set(retrieved[:k]) & set(gold)) / max(len(gold), 1)
```

- 报告：`R@1, R@3, R@5, R@10, R@20`

### 5.3 `Precision@K`

$$
\text{Precision@K}(q_i) = \frac{| \{r \in R_i[:K] \mid r \in G_i\} |}{K}
$$

### 5.4 `MRR`

$$
\text{MRR} = \frac{1}{|Q|} \sum_{i} \frac{1}{\text{rank}_i}
$$

`rank_i` 是首个相关结果在 `R_i` 中的位置（1-indexed），未命中按 0。

### 5.5 `NDCG@K`

```python
import numpy as np

def dcg(rels, k):
    rels = np.asarray(rels)[:k]
    return float(np.sum((2**rels - 1) / np.log2(np.arange(2, len(rels)+2))))

def ndcg(retrieved, graded, k):
    rels = [graded.get(r, 0) for r in retrieved[:k]]
    ideal = sorted(graded.values(), reverse=True)[:k]
    idcg = dcg(ideal, k)
    return dcg(rels, k) / idcg if idcg > 0 else 0.0
```

- `graded: dict[chunk_id -> relevance]`

### 5.6 `MAP@K`

```python
def average_precision(retrieved, gold, k):
    hits, s = 0, 0.0
    for i, r in enumerate(retrieved[:k], 1):
        if r in gold:
            hits += 1
            s += hits / i
    return s / max(len(gold), 1) if gold else 0.0

def map_at_k(rs, gs, k):
    return np.mean([average_precision(r, g, k) for r, g in zip(rs, gs)])
```

### 5.7 `Hit Rate@K`

```python
hit = [1 if set(r[:k]) & set(g) else 0 for r, g in zip(rs, gs)]
return np.mean(hit)
```

### 5.8 `Context Precision` & `Context Recall`

```python
def context_precision(retrieved, gold, k):
    return sum(1 for r in retrieved[:k] if r in gold) / k

def context_recall(retrieved, gold, k):
    return sum(1 for g in gold if g in retrieved[:k]) / max(len(gold), 1)
```

### 5.9 `Faithfulness (Proxy)`

- 把 ground-truth answer 拆成"原子 claim"
- 检索 top-K 中是否**支持**每个 claim
- 实现：先用句法切分，再用 NLI 模型（`MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`）打 label
- 简化版：claim 与 top-K 中任一段的 ROUGE-L ≥ 0.3 视为"支持"

### 5.10 `Answer Relevancy (Proxy)`

$$
\text{Rel}(q) = \frac{1}{K} \sum_{i=1}^{K} \cos(E(q), E(d_i))
$$

$E(\cdot)$ 为同一 embedding 模型，$d_i$ 为 top-K 第 i 个 chunk。

### 5.11 `Hallucination Risk`

- query 提取关键词（jieba + 停用词）
- top-K 中不含**任一**关键词的比例
- **建议**：< 0.20

### 5.12 `Refusal Accuracy`

- 负样本 query（库中无答案）
- top-K 中**不应**出现与 query 强相关但实际错误的文档
- 用 `Answer Relevancy` 阈值判断：> 0.7 视为"幻觉式误召"
- **目标**：≥ 0.80

### 5.13 `rerank.ndcg_gain`

$$
\Delta = \text{NDCG@10}_{\text{after\_rerank}} - \text{NDCG@10}_{\text{before\_rerank}}
$$

实现：先在 `model_service.rerank` 调用前后抓两组排序，分别计算 NDCG@10。

### 5.14 `rerank.score_calibration`

- 抽样 50 条 query × 20 chunk，手工标注 0/1/2/3
- 计算 rerank sigmoid 分数与人工等级 Spearman 相关系数
- **目标**：ρ ≥ 0.50

---

## 6. 报告汇总字段

每次评估 `metrics.json` 至少包含：

```json
{
  "version": "eval_20260609_120000_abc1234",
  "timestamp": "2026-06-09T12:00:00+08:00",
  "app_version": "1.0.0",
  "milvus_version": "2.4.x",
  "embedding_model": "BAAI/bge-large-zh-v1.5",
  "reranker_model": "BAAI/bge-reranker-large",
  "config_snapshot": { "...": "..." },
  "dataset": { "queries": 200, "corpus": 500 },
  "metrics": {
    "L0": { "...": "..." },
    "L1": { "...": "..." },
    "L2": { "...": "..." },
    "L3": { "...": "..." },
    "L4": { "...": "..." }
  },
  "regression": { "vs_baseline": { "NDCG@10": 0.012, "...": "..." } }
}
```

---

## 7. 判定矩阵速查

| 等级 | 含义 | 触发条件（任一） |
| --- | --- | --- |
| ✅ Pass | 通过 | 所有强制项指标达标 |
| 🟡 Warn | 警告 | 1 项不达标且偏差 < 10% |
| 🔴 Fail | 失败 | 1 项不达标且偏差 ≥ 10% / 出现 5xx 率 > 1% / 安全用例失败 |

判定结果写入 `report.md` 顶部。
