# RagFlow API 评估方案（Evaluation Plan）

> 版本：v1.0.0 · 起草日期：2026-06-09 · 适用项目版本：`app_version=1.0.0`
> 维护人：RagFlow API 评测组
> 关联文档：[指标参考](metrics_reference.md) · [测试集设计](test_datasets.md) · [基准场景](benchmark_scenarios.md) · [报告模板](report_template.md) · [变更日志](CHANGELOG.md)

---

## 0. 方案目的与读者

本方案用于对 **RagFlow API**（基于 Milvus + BGE 系列模型的本地化 Dify 外部知识库 API）进行**可重复、可量化、可回归**的评估。回答四个核心问题：

1. **答得对不对** — 检索 / 排序 / 端到端生成的质量如何？
2. **答得快不快** — 性能、吞吐、资源占用是否满足生产要求？
3. **接得住接不稳** — 系统的稳定性、可靠性、API 协议符合性如何？
4. **守得住守不住** — 鉴权、输入校验、敏感数据治理是否存在漏洞？

读者：算法工程师、后端工程师、QA、SRE、合规与产品负责人。

---

## 1. 项目与现状速览

| 维度 | 现状 |
| --- | --- |
| API 框架 | FastAPI（`app/main.py`），监听 `0.0.0.0:8002`，单 worker |
| 业务接口 | `POST /retrieval`、`/documents/store`、`/documents/update`、`/documents/delete` |
| 协议 | 兼容 Dify 外部知识库 API v1（`Bearer` 鉴权 + JSON 响应） |
| 检索链路 | query → `BGE-large-zh-v1.5`（1024 维）→ Milvus `vector` 字段 ANN（IP, nprobe=16）→ `BGE-reranker-large` 重排 → `score_threshold` 过滤 → 返回 Top-K |
| 关键参数 | `top_k`（默认 10）、`score_threshold`（默认 0.0）、`bm25_weight=0.5`、`vector_weight=0.5`、`use_fp16=true` |
| 知识域 | 药品 GMP 体系（`docs/GMP/SOP`、`docs/GMP/SMP`），主要文档为 `.docx` |
| 鉴权 | 多 Key 逗号分隔（`API_KEYS`），`Authorization: Bearer {KEY}` |
| 关键依赖 | `pymilvus >= 2.4`、`sentence-transformers`、`FlagEmbedding`、`rank_bm25`、`jieba` |

### 1.1 已识别的实现 Gap（评估时需重点关注）

> 这些是阅读源码后发现的**潜在风险 / 不一致**，评估时需独立验证并形成基线记录。

| # | 问题 | 位置 | 评估意义 |
| --- | --- | --- | --- |
| G1 | `MilvusService.search_documents` **仅做稠密向量检索**，`compute_bm25_sparse` 定义了但未在检索链路中调用 | `app/services/milvus_service.py:166` | "BM25+向量" 是声明能力，评估必须验证是否实际融合 |
| G2 | `score_threshold=0.0` 默认值会让 Reranker 排序结果"原样"返回，等价于未过滤 | `app/core/config.py:29` | 评估需扫描不同阈值下的命中率曲线 |
| G3 | `update_documents` 采用"按 title 删除后插入"的两步式更新，**非原子**；并发场景下可能丢数据 | `app/services/milvus_service.py:235` | 评估需做并发写一致性测试 |
| G4 | `delete_documents` 通过 `int(cid)` 区分"按 id 删除"和"按 title 删除"，数字字符串的 title 会被误判 | `app/services/milvus_service.py:299` | 评估需构造数字 title 的边界用例 |
| G5 | `revectorize=false` 时把 `vector` 字段写成 `[0.0]*1024` 占位，会污染向量检索 | `app/api/documents.py:247` | 评估需验证更新后该记录仍可被检索到的概率 |
| G6 | `metadata_condition` 字段定义了 schema，但后端**未实现过滤逻辑** | `app/api/documents.py:60` | 评估需验证 metadata 过滤是否生效 |
| G7 | `extract_subject` 用 `json.dumps({"subject":..., "file_path":...})` 序列化进 `subject` VARCHAR 字段，schema 描述与实际存储不一致 | `app/services/milvus_service.py:16` | 评估需对老数据 / 备份的兼容性进行回归 |

---

## 2. 评估总览

### 2.1 评估层级（自下而上）

```
┌──────────────────────────────────────────────────────────┐
│ L4 端到端问答质量  ── Faithfulness / Answer Relevancy …  │  ← 业务价值
├──────────────────────────────────────────────────────────┤
│ L3 检索 + 重排质量 ── Recall@K / NDCG@K / MRR …          │  ← 核心算法
├──────────────────────────────────────────────────────────┤
│ L2 数据 & 索引质量 ── 分块质量 / 覆盖率 / 索引一致性      │  ← 数据资产
├──────────────────────────────────────────────────────────┤
│ L1 系统 & 接口质量 ── 时延 / 吞吐 / 稳定性 / 协议符合性   │  ← 工程能力
├──────────────────────────────────────────────────────────┤
│ L0 安全 & 治理     ── 鉴权 / 输入校验 / 注入 / 越权       │  ← 合规底线
└──────────────────────────────────────────────────────────┘
```

### 2.2 评估方式

| 方式 | 说明 | 工具 |
| --- | --- | --- |
| **离线评估（Offline）** | 在标注测试集上批量跑检索/重排，得到检索质量指标 | `pytest` + 自研 harness、可能引入 `RAGAS` |
| **在线评估（Online）** | 部署到准生产环境，压测 / 灰度采集真实请求 | `locust`（压测）、`uvicorn`（被测对象） |
| **回归评估（Regression）** | 每次模型 / 检索参数变更后自动跑基线对比 | `pytest` + `pytest-benchmark` + CI |
| **人工评估（Human）** | 对低频、长尾、领域专业问题做专家打分 | 内部 SOP 专家双盲打分 |
| **A/B 评估** | 多个权重（`bm25_weight`/`vector_weight`）下并发分流 | 流量镜像 + 指标对比 |

---

## 3. 评估维度与指标（按层级展开）

> **下表为总览**，每个指标**计算公式 / 测量方法 / 判定阈值 / 参考实现**见 [metrics_reference.md](metrics_reference.md)。

### L0 · 安全 & 治理

| 指标 | 计算/方法 | 通过阈值 | 工具 |
| --- | --- | --- | --- |
| `auth.pass_rate` | 用合法 / 非法 / 缺失 / 过期 Key 探测 4 类请求的成功率 | 非法 100% 拒绝，合法 100% 通过 | `pytest` |
| `authz.tenant_isolation` | 不同 `knowledge_id` 下的文档不串 | 0 串数据 | 自研 |
| `input.safety` | Fuzzing：超长 / 畸形 JSON / SQL/表达式注入 | 不抛 5xx，不越权 | `boofuzz` / `hypothesis` |
| `pii.leakage` | 检索内容是否含身份证 / 手机号等 | 0 命中（按合规策略） | 正则 + 字典 |
| `audit.coverage` | 所有写接口是否打点（knowledge_id、操作类型、chunk_ids） | 100% | 日志抽检 |

### L1 · 系统 & 接口质量

| 指标 | 计算/方法 | 通过阈值 | 工具 |
| --- | --- | --- | --- |
| `perf.latency_p50/p95/p99` | `/retrieval` 端到端响应时间（含向量化 + Milvus + rerank） | p95 ≤ 800ms（top_k=10，本地 GPU） | `locust` + `prometheus_client` |
| `perf.cold_start` | 冷启动 → 首个 200 响应 | ≤ 30s（首次含模型加载） | `pytest` |
| `perf.qps` | 持续 5 分钟并发下的最大稳定 QPS | ≥ 10 QPS（top_k=10，单 worker） | `locust` |
| `perf.embedding_throughput` | `encode_texts` 文本/秒 | ≥ 200 句/秒（GPU fp16） | `pytest-benchmark` |
| `perf.rerank_latency` | 对 50 候选 rerank 耗时 | p95 ≤ 300ms | `pytest-benchmark` |
| `perf.resource` | CPU/GPU/内存/显存 | GPU 显存 ≤ 6GB（fp16） | `nvidia-smi` / `psutil` |
| `rel.error_rate` | 5xx / 4xx 比例 | 5xx < 0.1%，4xx 按预期分布 | 日志统计 |
| `rel.recovery` | 注入 Milvus 故障后恢复时间 | ≤ 10s | 混沌测试 |
| `api.dify_compliance` | Dify 外部知识库 API v1 协议一致性 | 100% schema match | `schemathesis` / `dify-cli` |
| `api.contract` | 请求/响应字段、错误码 1001/1002/2001 | 与 [Dify 规范](https://docs.dify.ai) 一致 | 协议用例 |

### L2 · 数据 & 索引质量

| 指标 | 计算/方法 | 通过阈值 | 工具 |
| --- | --- | --- | --- |
| `data.chunk_size_dist` | 文档分块长度分布 | 中位数 200–500 字符，p95 ≤ 1200 | `pandas` |
| `data.chunk_overlap` | 相邻块重叠率 | 10%–20% | 自研 |
| `data.dedup_rate` | 重复 chunk 比例 | < 1% | `MinHash` / 精确去重 |
| `data.subject_coverage` | subject 字段填充率 | ≥ 95% | SQL 聚合 |
| `data.embedding_consistency` | 同一文本两次 embedding 余弦相似度 | ≥ 0.9999 | 抽样 |
| `data.milvus_schema_consistency` | 集合 schema 与代码期望一致 | 字段、维度、索引类型 100% 匹配 | `pymilvus` |
| `data.backup_restore` | 备份 → 新集合恢复成功率 | 100% 数据 + 索引 | `milvus_backup` |

### L3 · 检索 + 重排质量（核心）

#### 3.1 测试集（Ground Truth）

构造"查询 - 相关 chunk_id 列表（含等级）"的标准测试集：

- **Factual**（事实型）：`地氯雷他定检验标准操作规程的版本号是多少？`
- **Procedural**（流程型）：`BG-260E 包衣机清洁的标准流程是什么？`
- **Definitional**（定义型）：`什么是 SOP？SMP 与 SOP 的区别？`
- **Numerical**（数值型）：`二氧化硫残留量测定法的检测限？`
- **Long-tail**（长尾型）：低频 / 专有名词 / 缩写
- **Negative**（负样本）：检索库中**无答案**的查询，用于测拒答 / 不乱答
- **Adversarial**（对抗型）：错别字、跨语种（中英混排）、近义改写

每个 query 标注：
```json
{
  "query_id": "q_001",
  "query": "...",
  "type": "procedural",
  "gold_chunks": [
    {"chunk_id": "SOPQC-YL003-3-03::p3", "relevance": 3},
    {"chunk_id": "SOPQC-YL003-3-03::p5", "relevance": 2}
  ],
  "expected_answer_keywords": ["包衣", "清洁", "验证"],
  "difficulty": "medium"
}
```

详见 [test_datasets.md](test_datasets.md)。

#### 3.2 检索质量指标

| 指标 | 公式 | 业务含义 | 目标 |
| --- | --- | --- | --- |
| **Recall@K** | `\|retrieved ∩ gold\| / \|gold\|` | 前 K 条里能召回多少相关 | R@10 ≥ 0.85 |
| **Precision@K** | `\|retrieved ∩ gold\| / K` | 前 K 条里准的有多少 | P@10 ≥ 0.60 |
| **MRR** | `mean(1/rank_of_first_relevant)` | 首个相关结果排多靠前 | ≥ 0.70 |
| **NDCG@K** | 折扣累积增益 / 理想折扣累积增益 | 综合位置 + 多级相关性 | ≥ 0.80 |
| **MAP@K** | 各 query AP 的均值 | 整体排序质量 | ≥ 0.75 |
| **Hit Rate@K** | 至少召回一个相关的 query 占比 | 兜底可用性 | ≥ 0.95 |
| **Coverage@R** | 检索返回的非空率 | 防止空召回 | ≥ 0.90 |

#### 3.3 重排质量指标

| 指标 | 计算 | 目标 |
| --- | --- | --- |
| `rerank.ndcg_gain` | `NDCG@K_after − NDCG@K_before` | ≥ +0.05 |
| `rerank.top1_swap_rate` | 重排后 top-1 改变的占比 | 监控漂移 |
| `rerank.score_calibration` | rerank 分数与人工相关性 Spearman | ≥ 0.50 |
| `rerank.latency_p95` | 50 候选 rerank 耗时 | ≤ 300ms |

#### 3.4 消融实验（必做）

| 编号 | 配置 | 目的 |
| --- | --- | --- |
| A1 | 仅稠密向量（当前默认） | 基线 |
| A2 | 稠密 + reranker（当前实现） | 重排增益 |
| A3 | 真实 BM25 + 向量融合 | 验证 G1 |
| A4 | 纯 BM25 | 词典兜底 |
| A5 | 阈值扫描 0.0/0.2/0.4/0.6 | 验证 G2 |
| A6 | `bm25_weight ∈ {0.0, 0.3, 0.5, 0.7, 1.0}` | 找最优融合权重 |

### L4 · 端到端问答质量

> 本服务不直接生成答案，但作为 Dify 外部 KB，**检索上下文**是 LLM 答案质量的天花板。评估方式：

| 指标 | 公式 / 方法 | 目标 |
| --- | --- | --- |
| **Context Precision** | `\|relevant_in_top_k\| / k` | ≥ 0.80 |
| **Context Recall** | `\|gold_covered_by_top_k\| / \|gold\|` | ≥ 0.85 |
| **Faithfulness (Proxy)** | 用 ground-truth answer 拆分 claim → 检查 top-K 中是否支持 | ≥ 0.75 |
| **Answer Relevancy (Proxy)** | query 与 top-K 内容平均余弦相似度 | ≥ 0.65 |
| **Hallucination Risk** | top-K 中**不含** query 关键词的比例 | < 0.20 |
| **Refusal Accuracy** | 无答案查询中，前 K 不返回"看似相关但错误"内容 | ≥ 0.80 |

---

## 4. 评估流程

### 4.1 单次评估生命周期

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 1. 准备  │ → │ 2. 注入  │ → │ 3. 运行  │ → │ 4. 测量  │ → │ 5. 报告  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
  加载模型      导入测试集     调用 API         抓取指标       写入 Reports
  预热索引      构建 gold      记录 trace       计算 NDCG      生成基线
```

#### Step 1 · 准备

1. 启动 Milvus 并确保 `policy_documents` 集合存在且加载完成
2. `python -c "from app.main import app"` 预热模型（约 30s）
3. 发送 5 条预热请求，避免首请求冷启

#### Step 2 · 注入测试集

- 评测库与生产库**严格隔离**：使用 `MILVUS_COLLECTION_NAME=eval_<uuid>` 单独建集合
- 把 `data/eval_corpus.jsonl` 灌入（沿用 `store_documents` 接口，闭环验证 API）
- 把 `data/eval_queries.jsonl`（gold 标准）加载到 `eval/test_queries.jsonl`

#### Step 3 · 运行

- **离线**：调用 `/retrieval`，记录每个 query 的 top-K 及耗时，dump 到 `Reports/_artifacts/run_<ts>.jsonl`
- **在线**：用 `locust` 模拟业务流量，固定数据集循环跑 5 分钟

#### Step 4 · 测量

```python
# pseudo
metrics = Evaluator(eval_set).run(
    endpoints=[("retrieval", "http://localhost:8002/retrieval")],
    top_ks=[1, 3, 5, 10, 20],
    rerank=True,
)
metrics.dump("Reports/reports/eval_<ts>/metrics.json")
```

#### Step 5 · 报告

- 渲染至 `Reports/reports/eval_<ts>/report.md`（按 [report_template.md](report_template.md)）
- 与基线比对（见 §6 版本管理），差异 > 阈值（如 NDCG@10 ↓ 0.05）标红

### 4.2 评估矩阵（频次建议）

| 维度 | 频率 | 触发条件 |
| --- | --- | --- |
| L0 安全 | 每次发版 | 强制 |
| L1 性能 / 稳定性 | 每次发版 | 强制 |
| L3 检索 / 重排 | 每次发版 + 模型/参数变更 | 强制 |
| L2 数据质量 | 数据集更新时 | 强制 |
| L4 端到端 | 大版本（x.0） | 推荐 |
| 消融 A1–A6 | 算法变更 | 必做 |

---

## 5. 工具与代码组织

```
ragflowapi/
├── app/                       # 业务代码
├── Reports/                   # 评估报告与方案（git tracked）
│   ├── README.md
│   ├── evaluation_plan.md     # ← 本文件
│   ├── metrics_reference.md
│   ├── test_datasets.md
│   ├── benchmark_scenarios.md
│   ├── report_template.md
│   ├── CHANGELOG.md
│   └── reports/               # 历史评估结果（按时间戳归档）
│       └── eval_20260609_xxx/
│           ├── metrics.json
│           ├── report.md
│           └── config_snapshot.yaml
├── eval/                      # 评估代码（不在 git tracked 范围，团队约定）
│   ├── harness.py
│   ├── metrics.py
│   ├── datasets/
│   │   ├── eval_corpus.jsonl
│   │   └── eval_queries.jsonl
│   ├── locustfile.py
│   └── reports/
└── tools/
    └── report_renderer.py
```

> 评估代码可放在 `eval/`（建议建一个独立 Python 包），不强制纳入 git；本评估方案仅约束**输出**与**结果文件**入 git。

### 5.1 推荐技术栈

| 用途 | 工具 |
| --- | --- |
| 协议契约 | `schemathesis` / `pydantic` |
| 离线评测 | `pytest` + 自研 `Evaluator` |
| RAG 评估 | `ragas`（可选）、`langfuse`（在线追踪） |
| 压测 | `locust` |
| 性能采样 | `py-spy` / `nvidia-smi dmon` |
| 监控 | `prometheus_client` + `grafana` |
| CI | `GitHub Actions` / `GitLab CI` |
| 报告 | `Jinja2` 渲染 Markdown + `matplotlib` 出图 |

---

## 6. 版本控制 & 基线管理

### 6.1 报告与方案如何版本化

| 类别 | 版本号 | 命名 | 入 git |
| --- | --- | --- | --- |
| 评估方案 | `vMAJOR.MINOR.PATCH`（语义化版本） | `evaluation_plan.md` 单文件，变更写 `CHANGELOG.md` | ✅ |
| 历史评估结果 | 时间戳 + 短 hash | `reports/eval_YYYYMMDD_HHMMSS_<hash>/` 目录 | ✅ |
| 大产物 | — | `Reports/_artifacts/`（`.gitignore` 排除） | ❌ |

### 6.2 基线（Baseline）机制

- 每次发版时由 CI **冻结当前指标**到 `Reports/reports/eval_<ts>/baseline.json`
- 下次评估自动 diff，输出 `Δ NDCG@10 = -0.02 🔴`
- 基线晋升规则：连续 3 个发版指标稳定 + 专家评审通过

### 6.3 当前基线（首版占位）

> 首次评估前先用一组固定 query 跑 1 次，把结果写入 `Reports/reports/baseline_init/`，作为后续比对锚点。

---

## 7. 风险与注意事项

1. **标注一致性**：gold 标准由 ≥ 2 名 SOP 专家独立标注，Krippendorff's α ≥ 0.7 才入库
2. **数据漂移**：每季度抽样 50 条核对库内容变化，必要时重建测试集
3. **模型升级**：换 embedding / reranker 必须重做 A1–A6 消融
4. **Milvus 升级**：升级前在镜像环境跑 `data.backup_restore` 与 `data.milvus_schema_consistency`
5. **公平对比**：所有对比实验必须**同一份测试集 + 同一份索引 + 同一台机器**

---

## 8. 上手执行清单（DoD）

- [ ] 准备 `eval/datasets/eval_queries.jsonl`（≥ 200 条）
- [ ] 在 `eval/datasets/eval_corpus.jsonl` 中准备测试语料（≥ 500 块）
- [ ] 实现 `eval/harness.py`（`Evaluator` 类，输出 `metrics.json`）
- [ ] 实现 `eval/metrics.py`（Recall@K、NDCG@K、MRR、Hit Rate、Context Precision/Recall）
- [ ] 写 `eval/locustfile.py`（覆盖三类场景：热查询、冷查询、混合负载）
- [ ] 接入 `tools/report_renderer.py` 输出 Markdown
- [ ] 接入 CI：每次 PR 自动跑 L0+L1+L3，主干自动归档到 `Reports/reports/`
- [ ] 评审通过后 `git commit` 首批 Reports
