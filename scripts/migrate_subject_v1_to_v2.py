#!/usr/bin/env python3
"""G7 数据迁移脚本：policy_documents v1 → v2（pymilvus 3.0 MilvusClient）

用途：
  - 把 subject 字段中"伪装的 JSON"（含 file_path）拆解为独立字段
  - 把数据从 v1 集合复制到 v2 集合
  - 校验两边数据一致性

v1 集合 schema（历史）:
  - id, title, text, vector, sparse_bm25, subject
  - subject 字段中可能存的是 JSON：{"subject": "...", "file_path": "..."}
    也可能直接是字符串

v2 集合 schema（目标）:
  - id, title, text, vector, sparse_bm25, subject, file_path
  - subject 纯字符串；file_path 独立字段

用法：
  python scripts/migrate_subject_v1_to_v2.py \\
      --source policy_documents_v1 \\
      --target policy_documents_v2 \\
      --batch 500 \\
      --dry-run
"""

import argparse
import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from pymilvus import (
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    MilvusClient,
)
from pymilvus.milvus_client.index import IndexParams

# ==================== 日志 ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("migrate_v1_to_v2")


# ==================== 字段拆分 ====================


def split_subject_field(raw: str) -> Tuple[str, Optional[str]]:
    """从 v1 subject 字段中拆出 (subject, file_path)

    兼容两种历史：
      1) JSON: {"subject":"QC","file_path":"docs/.../SOP.docx"}
      2) 纯字符串
    """
    if not raw:
        return "", None
    raw = raw.strip()
    if not raw:
        return "", None
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return (
                    str(obj.get("subject", "") or ""),
                    obj.get("file_path"),
                )
        except json.JSONDecodeError:
            pass
    return raw, None


# ==================== v2 Schema 工厂 ====================


def build_v2_schema(dim: int) -> CollectionSchema:
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=256),
        # BM25 Function 输入字段必须开启分析器
        FieldSchema(
            name="text",
            dtype=DataType.VARCHAR,
            max_length=65535,
            enable_analyzer=True,
            analyzer_params={"type": "chinese"},
        ),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="sparse_bm25", dtype=DataType.SPARSE_FLOAT_VECTOR),
        FieldSchema(name="subject", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=1024),
    ]
    functions = [
        Function(
            name="bm25_function",
            function_type=FunctionType.BM25,
            input_field_names=["text"],
            output_field_names=["sparse_bm25"],
        ),
    ]
    return CollectionSchema(
        fields=fields,
        functions=functions,
        description="Migrated policy_documents v2 (subject pure + file_path)",
    )


def build_v2_index_params() -> IndexParams:
    ip = IndexParams()
    ip.add_index(
        field_name="vector",
        index_type="IVF_FLAT",
        metric_type="IP",
        nlist=1024,
    )
    ip.add_index(
        field_name="sparse_bm25",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
        inverted_index_algo="DAAT_MAXSCORE",
    )
    return ip


# ==================== 迁移流程 ====================


def fetch_all_from_source(
    client: MilvusClient,
    source: str,
    batch: int,
) -> List[Dict[str, Any]]:
    """分批拉取源集合全部数据（按主键 id 翻页）"""
    stats = client.get_collection_stats(source)
    total = int(stats.get("row_count", 0))
    logger.info(f"源集合 {source} 共 {total} 条；开始分批拉取")

    rows: List[Dict[str, Any]] = []
    last_id = 0
    while True:
        chunk = client.query(
            collection_name=source,
            filter=f"id > {last_id}",
            limit=batch,
            output_fields=["id", "title", "text", "vector", "subject"],
        )
        if not chunk:
            break
        rows.extend(chunk)
        last_id = max(r["id"] for r in chunk)
        logger.info(
            f"  拉取进度: {len(rows)}/{total} "
            f"({100 * len(rows) / max(total, 1):.1f}%)"
        )
        if len(chunk) < batch:
            break
    return rows


def transform_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """拆分 subject 字段为 subject + file_path"""
    out: List[Dict[str, Any]] = []
    json_count = 0
    for r in rows:
        raw_subject = r.get("subject", "")
        subject, file_path = split_subject_field(raw_subject)
        if raw_subject.startswith("{"):
            json_count += 1
        out.append(
            {
                "title": r.get("title", ""),
                "text": r.get("text", ""),
                "vector": r.get("vector", []),
                "subject": subject,
                "file_path": file_path or "",
            }
        )
    logger.info(
        f"字段拆分完成：{len(rows)} 条，其中 {json_count} 条原本存为 JSON"
    )
    return out


def insert_into_target(
    client: MilvusClient,
    target: str,
    rows: List[Dict[str, Any]],
    batch: int,
    dry_run: bool,
) -> int:
    """把拆解后的数据写入目标集合"""
    if dry_run:
        logger.info(f"[DRY-RUN] 跳过实际写入 {len(rows)} 条")
        return 0

    written = 0
    for offset in range(0, len(rows), batch):
        chunk = rows[offset : offset + batch]
        client.insert(collection_name=target, data=chunk)
        client.flush(target)
        written += len(chunk)
        logger.info(
            f"  写入进度: {written}/{len(rows)} "
            f"({100 * written / max(len(rows), 1):.1f}%)"
        )
    return written


def verify(
    client: MilvusClient,
    source: str,
    target: str,
    sample_size: int = 100,
) -> bool:
    """抽样校验：源 title 与目标 title 一致 + subject 不再含 JSON 大括号"""
    sample = client.query(
        collection_name=source,
        filter="id > 0",
        limit=sample_size,
        output_fields=["title", "subject"],
    )
    if not sample:
        logger.info("源集合无数据，跳过校验")
        return True

    titles = [r["title"] for r in sample]
    titles_str = ", ".join([f'"{t}"' for t in titles])
    target_rows = client.query(
        collection_name=target,
        filter=f"title in [{titles_str}]",
        output_fields=["title", "subject", "file_path"],
    )
    target_map = {r["title"]: r for r in target_rows}

    bad_json = 0
    missing = 0
    for r in sample:
        t = r["title"]
        if t not in target_map:
            missing += 1
            continue
        tgt_subject = target_map[t].get("subject", "")
        if tgt_subject.startswith("{"):
            bad_json += 1

    logger.info(
        f"校验：抽样 {sample_size} 条 / 缺失 {missing} / 目标仍含 JSON {bad_json}"
    )
    return missing == 0 and bad_json == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="G7 数据迁移 v1 → v2（MilvusClient）")
    parser.add_argument("--source", required=True, help="源集合名（含 JSON 伪装的 v1）")
    parser.add_argument("--target", required=True, help="目标集合名（v2 schema）")
    parser.add_argument("--dim", type=int, default=1024, help="向量维度")
    parser.add_argument("--batch", type=int, default=500, help="分批大小")
    parser.add_argument("--host", default="localhost", help="Milvus 主机")
    parser.add_argument("--port", type=int, default=19530, help="Milvus 端口")
    parser.add_argument("--user", default="", help="Milvus 用户名")
    parser.add_argument("--password", default="", help="Milvus 密码")
    parser.add_argument(
        "--drop-target",
        action="store_true",
        help="如目标集合已存在则删除（慎用！）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只拉取与拆分，不实际写入",
    )
    args = parser.parse_args()

    # 1) 客户端
    uri = f"http://{args.host}:{args.port}"
    logger.info(f"连接 Milvus {uri} via MilvusClient")
    client = MilvusClient(
        uri=uri,
        user=args.user or None,
        password=args.password or None,
    )

    # 2) 校验源
    if not client.has_collection(args.source):
        logger.error(f"源集合 {args.source} 不存在")
        return 1
    src_stats = client.get_collection_stats(args.source)
    logger.info(
        f"源集合 {args.source}：row_count={src_stats.get('row_count', '?')}"
    )

    # 3) 准备目标
    target_exists = client.has_collection(args.target)
    if target_exists:
        if args.drop_target:
            logger.warning(f"--drop-target 开启，将删除既有 {args.target}")
            client.drop_collection(args.target)
            target_exists = False
        else:
            logger.info(f"目标 {args.target} 已存在，将直接写入")
    if not target_exists and not args.dry_run:
        schema = build_v2_schema(args.dim)
        index_params = build_v2_index_params()
        client.create_collection(
            collection_name=args.target,
            schema=schema,
            index_params=index_params,
        )
        logger.info(f"已创建目标集合 {args.target} 及索引")

    # 4) 拉取 + 拆分 + 写入
    t0 = time.perf_counter()
    rows = fetch_all_from_source(client, args.source, batch=args.batch)
    transformed = transform_rows(rows)
    written = insert_into_target(
        client, args.target, transformed, batch=args.batch, dry_run=args.dry_run
    )
    dt = time.perf_counter() - t0

    # 5) 校验
    if not args.dry_run and written > 0:
        ok = verify(client, args.source, args.target)
        if not ok:
            logger.error("校验失败！请人工核查")
            return 2

    # 6) 报告
    logger.info(
        f"完成：源 {len(rows)} → 目标 {written}，耗时 {dt:.1f}s"
    )
    if not args.dry_run:
        logger.info(
            f"下一步：\n"
            f"  1) 抽样对比 {args.source} vs {args.target} 内容\n"
            f"  2) 切流（重命名或 alias 切换）：\n"
            f"     - 方案 A：rename target → 主名\n"
            f"     - 方案 B：alias swap\n"
            f"  3) 保留 {args.source} 只读 7 天后再 drop"
        )

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
