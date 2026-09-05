#!/usr/bin/env python3
"""S5 v1.4 数据迁移：policy_documents_v2 → policy_documents_v3

目的：
  v3 schema 新增 text_with_title 字段，BM25 Function 改吃该字段，
  让短 ID（"SMPGW043-3-00"）和中文长标题（"生产前检查场管理规程"）
  都能被 BM25 强匹配。

流程：
  1. 连接 v2 集合，统计总条数
  2. 分批拉数据（避免一次拉 5000+ 撑爆内存）
  3. 按 v3 schema 重建 v3 集合（drop+create）
  4. 用 _build_row 写入（自动添加 text_with_title 字段）
  5. 校验：v2 / v3 row_count 一致 + 抽样验证 text_with_title 拼接正确

用法：
  MILVUS_COLLECTION_NAME=policy_documents_v2 \\
  TARGET_COLLECTION_NAME=policy_documents_v3 \\
  python scripts/migrate_v2_to_v3.py
"""
import os
import sys
import time
from pathlib import Path

# 让脚本能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.milvus_service import MilvusService


BATCH = 500


def main():
    src_name = os.environ.get("MILVUS_COLLECTION_NAME", "policy_documents_v2")
    tgt_name = os.environ.get("TARGET_COLLECTION_NAME", "policy_documents_v3")
    print(f"[migrate] source={src_name}  target={tgt_name}")

    # ===== 1. 连接 v2 集合，统计总条数 =====
    os.environ["MILVUS_COLLECTION_NAME"] = src_name
    # 重新读 settings
    from pydantic_settings import BaseSettings
    s = settings.model_copy(update={"milvus_collection_name": src_name})
    # 直接覆盖 settings（不在原 env 模式重建）
    settings.milvus_collection_name = src_name

    src = MilvusService()  # 用 settings.milvus_collection_name = src_name
    src.connect()
    src.create_collection()
    src_stats = src.client.get_collection_stats(src_name)
    total = src_stats.get("row_count", 0)
    print(f"[migrate] 源集合 {src_name} 总条数: {total}")
    if total == 0:
        print("[migrate] 源集合为空，退出")
        return

    # ===== 2. 分批拉数据 =====
    print(f"[migrate] 拉取全量数据（分批 {BATCH}）...")
    all_rows = []
    offset = 0
    t0 = time.time()
    while offset < total:
        batch = src.client.query(
            collection_name=src_name,
            output_fields=["title", "text", "vector", "subject", "file_path"],
            limit=BATCH,
            offset=offset,
        )
        if not batch:
            break
        all_rows.extend(batch)
        offset += len(batch)
        if len(all_rows) % 2000 == 0 or len(all_rows) == total:
            print(f"  拉取 {len(all_rows)}/{total}  耗时 {time.time()-t0:.1f}s")
    print(f"[migrate] 拉取完成：{len(all_rows)} 条  耗时 {time.time()-t0:.1f}s")
    src.close()

    # ===== 3. 重建 v3 集合 =====
    print(f"[migrate] 重建目标集合 {tgt_name} ...")
    settings.milvus_collection_name = tgt_name
    tgt = MilvusService()
    tgt.connect()
    # 如果存在则 drop
    if tgt.client.has_collection(tgt_name):
        print(f"  {tgt_name} 已存在，先 drop ...")
        tgt.client.drop_collection(tgt_name)
    tgt.create_collection()  # 自动按 v3 schema 创建
    print(f"  {tgt_name} 已创建（v3 schema）")

    # ===== 4. 批量写入 =====
    print(f"[migrate] 写入数据 ...")
    # 把 pymilvus 返回的 row 格式转换为 doc 格式（key='content' 等）
    docs = []
    for r in all_rows:
        # 'text' → 'content'（匹配 _build_row 期望的 key）
        docs.append({
            "title": r.get("title", ""),
            "content": r.get("text", ""),  # text 字段重命名
            "vector": r.get("vector", []),
            "subject": r.get("subject", ""),
            "file_path": r.get("file_path", ""),
        })

    # 批量插入（BATCH 一次）
    inserted = 0
    t1 = time.time()
    for i in range(0, len(docs), BATCH):
        batch = docs[i:i+BATCH]
        titles = tgt._prepare_titles(batch)
        use_v3 = True
        rows = [tgt._build_row(t, d, use_v3=use_v3) for t, d in zip(titles, batch)]
        tgt.client.insert(collection_name=tgt_name, data=rows)
        inserted += len(batch)
        if inserted % 1000 == 0 or inserted == len(docs):
            print(f"  写入 {inserted}/{len(docs)}  耗时 {time.time()-t1:.1f}s")
    tgt.client.flush(tgt_name)
    tgt.client.load_collection(tgt_name)  # 必须 load 才能检索
    print(f"[migrate] 写入完成：{inserted} 条  耗时 {time.time()-t1:.1f}s")

    # ===== 5. 校验 =====
    print(f"[migrate] 校验 ...")
    tgt_stats = tgt.client.get_collection_stats(tgt_name)
    print(f"  v3 row_count: {tgt_stats.get('row_count', 0)}")
    if tgt_stats.get("row_count") != total:
        print(f"  ⚠ 条数不一致：v2={total}  v3={tgt_stats.get('row_count')}")
    # 抽样验证
    sample = tgt.client.query(
        collection_name=tgt_name,
        output_fields=["title", "text_with_title"],
        limit=3,
    )
    for s in sample:
        title = s.get("title", "")
        twt = s.get("text_with_title", "")
        ok = twt.startswith(title)
        print(f"  抽样: title='{title[:30]}'  text_with_title.startswith(title)={ok}")

    tgt.close()
    print(f"[migrate] 全部完成。切换方式：")
    print(f"  export MILVUS_COLLECTION_NAME={tgt_name}")
    print(f"  或在 .env 设 MILVUS_COLLECTION_NAME={tgt_name}")


if __name__ == "__main__":
    main()
