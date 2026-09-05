# 变更日志（CHANGELOG）

> 本文件记录 **Reports 目录**下所有文档 / 数据集 / 报告的版本变更。
> 格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
> 版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### 待办

- ~~首版基线评估（baseline_init）~~ — 推迟到 Phase 1 验证后
- 接入 `ragas` 或自研 NLI 评估 L4
- 引入 schemathesis 跑 S9 协议契约
- 引入 locust 跑 S3 / S4 压测
- 自动化报告渲染 `tools/report_renderer.py`

---

## [1.1.0] - 2026-06-09

### Added

- **G7 · subject 字段治理**
  - `app/core/config.py`：新增 `milvus_collection_alias` / `enable_v2_schema`；默认 collection 统一为 `policy_documents`
  - `app/services/milvus_service.py`：
    - 删除 `_serialize_subject` / `_deserialize_subject` JSON 序列化
    - 新增 `_build_v2_schema` 工厂：`subject` 还原为纯 VARCHAR(256)；新增 `file_path` VARCHAR(1024) 独立字段
    - 集合创建逻辑：`enable_v2_schema=true` 时按 v2 schema 自动建集合 + 双索引（IVF_FLAT + SPARSE_INVERTED_INDEX）
    - BM25 Function：`FunctionType.BM25`，`input=text` → `output=sparse_bm25`
  - `app/api/documents.py`：`_build_doc_dict` 统一构造写入字典（subject / file_path 独立）
  - `.env.example`：补齐 v2 相关环境变量
  - `scripts/migrate_subject_v1_to_v2.py`：JSON 拆解 + 分批回填 + 抽样校验

- **G1 · 真正混合检索（Milvus Hybrid Search + RRF）**
  - `app/core/config.py`：`enable_hybrid` / `hybrid_dense_limit` / `hybrid_sparse_limit` / `rrf_k`
  - `app/services/milvus_service.py`：新增 `hybrid_search(query_text, query_embedding, top_k, filter_expr=None)`
    - `AnnSearchRequest` × 2（dense + sparse_bm25）
    - `RRFRanker(k=60)` 融合
    - 支持 `filter_expr`（G6 预留）
  - `app/services/milvus_service.py`：`search_documents` 标 deprecated
  - `app/api/documents.py`：`/retrieval` 改调 `hybrid_search`，多召 3× 给 reranker 留余地

- **G3 · update 改用 upsert（原子性）**
  - `app/services/milvus_service.py`：`update_documents` 改 `pymilvus.upsert`，单次原子调用，记录 `upsert_count`

- **G5 · 修复 0 向量占位污染（顺手解决）**
  - `app/services/milvus_service.py`：新增 `fetch_vectors_by_titles`
  - `app/api/documents.py`：`revectorize=false` 分支先按 title 拉取旧向量复用；不存在则返回 4xx

### Changed

- `app/core/config.py`：`app_version` 默认值更新为 `1.1.0`
- 数据写入字段顺序：title / text / vector / subject / file_path（`sparse_bm25` 由 BM25 Function 自动生成）
- 检索召回：默认 `max(top_k × 3, 20)` 给 reranker 留余地，再按 threshold 过滤 + top_k 截断

### Security

- `_build_doc_dict` 中 `file_path` 优先取 `chunk.file_path`（API 字段），其次 `metadata.file_path` / `metadata.source_path`，最后空字符串

### Migration

- 切流步骤（运维）：
  1. `python scripts/migrate_subject_v1_to_v2.py --source policy_documents --target policy_documents_v2 --batch 500 --dry-run`
  2. 抽样验证
  3. 去掉 `--dry-run` 实际写入
  4. alias 切换或重命名
  5. 保留源集合 7 天只读后再 drop

### Notes

- pymilvus 实测版本 3.0.0，`Function` / `FunctionType.BM25` / `RRFRanker` / `hybrid_search` 均可用
- 旧 `search_documents` 保留一个版本，配置 `enable_hybrid=false` 时回退
- `delete_documents` 仍按 title 删除（G4 待 Phase 2 实施 id_type 区分）

### Changed (hotfix)

- **迁移到 pymilvus 3.0 MilvusClient API**（3.1 将移除 ORM 风格）
  - `app/services/milvus_service.py`：
    - 用 `MilvusClient(uri=..., user=..., password=...)` 取代 `connections.connect`
    - 移除 `Collection` 直接持有，CRUD 全部走 `client.xxx(...)`
    - `create_collection` 一次性传入 `schema` + `index_params`（`IndexParams` 对象）
    - `insert` / `upsert` 数据格式：`List[Dict]`（行 dict）取代 `List[List]`（列存）
    - `query` / `delete` / `search` 的 `expr=` → `filter=`
    - `search` / `hybrid_search` 结果中 `hit.score` → `hit.distance`（兼容取两键）
    - 移除 `Collection.load()`（MilvusClient 自动管理）
    - `close()` 调 `client.close()`
  - `scripts/migrate_subject_v1_to_v2.py`：同步迁移到 MilvusClient
    - 翻页策略：`id > last_id` 过滤循环取代 `offset + limit`（MilvusClient 无 offset）
  - 验证：`python -W default` 加载无 `PyMilvusDeprecationWarning`

### Fixed (hotfix 2)

- **BM25 Function 输入字段必须开启 analyzer**（Milvus 2.4+ 强制要求）
  - 报错：`MilvusException: (code=65535, message=BM25 function input field must set enable_analyzer to true)`
  - 修复：`app/services/milvus_service.py` 与 `scripts/migrate_subject_v1_to_v2.py` 的 `_build_v2_schema` / `build_v2_schema`
  - 改动：`text` 字段加 `enable_analyzer=True` + `analyzer_params={"type": "chinese"}`
  - 验证：`text.enable_analyzer is True` 且 `params.analyzer_params='{"type":"chinese"}'`

### Verification

- ✅ Python AST 语法检查：milvus_service.py / documents.py / config.py / migrate_subject_v1_to_v2.py
- ✅ 导入扫描：settings / _build_v2_schema / MilvusService 字段与方法齐全
- ✅ FastAPI 启动：路由 `/retrieval` `/documents/store` `/documents/update` `/documents/delete` 全部注册
- ⏳ 集成测试：需在 Milvus 实例上跑 S2 / S3 / S5 / S6 基准（见 [benchmark_scenarios.md](./benchmark_scenarios.md)）

---

## [1.0.0] - 2026-06-09

### Added

- **方案文档**
  - `Reports/evaluation_plan.md`：5 层级（L0–L4）评估框架、版本控制机制、DoD 清单
  - `Reports/metrics_reference.md`：~25 个指标的精确定义、公式、参考实现
  - `Reports/test_datasets.md`：corpus / queries / 留出 / 负样本 / 对抗样本规范
  - `Reports/benchmark_scenarios.md`：S1–S11 共 11 类基准测试场景
  - `Reports/report_template.md`：报告渲染模板 + config_snapshot 模板
  - `Reports/README.md`：Reports 目录导航与使用说明
- **基线 / 报告占位**
  - `Reports/reports/.gitkeep`：归档目录占位
- **风险清单**
  - 在 `evaluation_plan.md §1.1` 列出 7 项已识别实现 Gap（G1–G7）

### Notes

- 本次未生成任何实际评估结果（基线待跑）
- 评估代码未提交（约定放在 `eval/`，不入 git）
- 项目根 `.gitignore` 已配置：排除模型权重、备份、日志、评估大产物

### 关联代码现状

- `app_version=1.0.0`
- Embedding: `BAAI/bge-large-zh-v1.5` (1024 维)
- Reranker: `BAAI/bge-reranker-large` (max_length=512, sigmoid 归一到 0-1)
- Milvus collection: `policy_documents`（BM25 + dense 双向量）
- API 端点: `POST /retrieval`, `/documents/store|update|delete`
- 鉴权: Bearer Token（多 Key 逗号分隔）

---

## 模板

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- 新增内容

### Changed
- 修改内容

### Deprecated
- 即将废弃

### Removed
- 删除内容

### Fixed
- 修复内容

### Security
- 安全相关
```
