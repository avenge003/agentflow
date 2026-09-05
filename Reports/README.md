# Reports — RagFlow API 评估

> 本目录是 RagFlow API 的**评估方案、测试集规范、基准场景、报告模板与历史评估结果**的版本化归档。
> 维护人：RagFlow API 评测组

## 目录结构

```
Reports/
├── README.md                  # 本文件（导航 + 索引）
├── evaluation_plan.md         # 评估方案主文档（指标、流程、版本管理）
├── metrics_reference.md       # 指标参考手册（公式、实现、阈值）
├── test_datasets.md           # 测试数据集设计（gold 标注、负样本、对抗）
├── benchmark_scenarios.md     # 11 类基准测试场景与执行步骤
├── report_template.md         # 评估报告模板
├── CHANGELOG.md               # 方案 / 数据集 / 报告的版本变更日志
└── reports/                   # 历史评估结果（按时间戳归档）
    └── eval_<ts>_<short-hash>/
        ├── report.md
        ├── metrics.json
        ├── config_snapshot.yaml
        └── *.png
```

## 评估层级一览

| 层级 | 关注点 | 主要指标 |
| --- | --- | --- |
| L0 | 安全 & 治理 | 鉴权通过率、租户隔离、注入防御、PII 泄漏 |
| L1 | 系统 & 接口 | 延迟 p50/p95/p99、QPS、错误率、API 协议符合性 |
| L2 | 数据 & 索引 | 分块质量、覆盖率、schema 一致性、备份恢复 |
| L3 | 检索 + 重排 | Recall@K、Precision@K、MRR、NDCG@K、Hit Rate、Rerank Gain |
| L4 | 端到端问答 | Context Precision/Recall、Faithfulness、Hallucination Risk |

详见 [evaluation_plan.md](./evaluation_plan.md) 第 3 节。

## 5 分钟快速开始

1. 启动服务：`bash run.sh`
2. 准备数据集：参考 [test_datasets.md](./test_datasets.md) 准备 `eval/datasets/eval_queries.jsonl`
3. 运行离线评估：执行 `eval/harness.py`（详见 [evaluation_plan.md](./evaluation_plan.md) §4）
4. 渲染报告：用 [report_template.md](./report_template.md) 生成 `Reports/reports/eval_<ts>/report.md`
5. 提交报告：`git add Reports/reports/eval_<ts> && git commit -m "eval: <summary>"`

## 关联代码位置（参考）

- API 入口：[app/main.py](../../app/main.py)
- 检索实现：[app/api/documents.py](../../app/api/documents.py)
- Milvus 服务：[app/services/milvus_service.py](../../app/services/milvus_service.py)
- 模型服务：[app/services/model_service.py](../../app/services/model_service.py)
- 配置：[app/core/config.py](../../app/core/config.py)
- 鉴权：[app/middleware/auth.py](../../app/middleware/auth.py)

## 命名 / 版本约定

| 类别 | 命名 | 版本号 | 入 git |
| --- | --- | --- | --- |
| 方案 | `evaluation_plan.md` | SemVer (vMAJOR.MINOR.PATCH) | ✅ |
| 数据集 | `eval_queries_vX.Y` | vX.Y | ✅ |
| 评估结果 | `reports/eval_YYYYMMDD_HHMMSS_<hash>/` | 时间戳 + 短 hash | ✅ |
| 大产物（响应原文、图片） | `_artifacts/` | — | ❌（.gitignore） |

## 已识别风险（评估重点关注）

> 详细描述见 [evaluation_plan.md](./evaluation_plan.md) §1.1

- **G1** 实际只做稠密向量检索，`bm25_weight` 未生效
- **G2** `score_threshold=0.0` 默认不过滤
- **G3** `update_documents` 删除 + 插入非原子
- **G4** `delete_documents` 数字 / 字符串 title 区分有歧义
- **G5** `revectorize=false` 时把 vector 写成 0 占位
- **G6** `metadata_condition` schema 已定义但未实现
- **G7** subject 字段被 json 序列化存，schema 与实际不一致

## 评审与门禁

- `✅ Pass`：所有强制项达标
- `🟡 Warn`：偏差 < 10%，需负责人 approve
- `🔴 Fail`：偏差 ≥ 10% 或出现 5xx / 安全用例失败，自动 block PR
