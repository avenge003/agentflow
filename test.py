#!/usr/bin/env python3
"""Milvus数据库测试脚本"""

from pymilvus import connections, Collection
import json
import os
from datetime import datetime

# Milvus连接配置（支持从.env读取）
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_USER = os.getenv("MILVUS_USER", "root")
MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD", "Milvus")
COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "policy_documents")


def connect_milvus():
    """连接到Milvus数据库"""
    connections.connect(
        host=MILVUS_HOST,
        port=MILVUS_PORT,
        user=MILVUS_USER,
        password=MILVUS_PASSWORD,
        alias="default"
    )
    print(f"✅ 成功连接到Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
    return Collection(COLLECTION_NAME)


def get_collection_info(collection):
    """获取集合信息"""
    print("\n" + "=" * 50)
    print("集合信息")
    print("=" * 50)
    print(f"集合名称: {collection.schema.description or COLLECTION_NAME}")
    print(f"记录数: {collection.num_entities}")

    print("\n字段结构:")
    for field in collection.schema.fields:
        print(f"  - {field.name}: dtype={field.dtype}, primary={field.is_primary}")


def query_all(collection, limit=10):
    """查询所有数据"""
    print("\n" + "=" * 50)
    print(f"查询数据 (限制 {limit} 条)")
    print("=" * 50)

    results = collection.query(
        expr="id >= 0",
        output_fields=["id", "title", "text", "subject"],
        limit=limit
    )

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] ID: {r.get('id')}")
        print(f"    Title: {r.get('title', 'N/A')}")
        print(f"    Subject: {r.get('subject', 'N/A')}")
        text = r.get('text', '')[:100]
        print(f"    Text: {text}...")

    return results


def query_by_title(collection, title):
    """根据标题查询"""
    print("\n" + "=" * 50)
    print(f"按标题查询: {title}")
    print("=" * 50)

    results = collection.query(
        expr=f'title == "{title}"',
        output_fields=["id", "title", "text", "subject"]
    )

    if results:
        for r in results:
            print(f"\nID: {r.get('id')}")
            print(f"Title: {r.get('title')}")
            print(f"Subject: {r.get('subject')}")
            print(f"Text: {r.get('text')[:200]}...")
    else:
        print("未找到匹配的记录")

    return results


def search_by_text(collection, keyword, limit=10):
    """根据文本内容搜索"""
    print("\n" + "=" * 50)
    print(f"文本搜索: {keyword}")
    print("=" * 50)

    # 使用SQL-like查询
    results = collection.query(
        expr=f'title like "%{keyword}%"',
        output_fields=["id", "title", "text", "subject"],
        limit=limit
    )

    print(f"找到 {len(results)} 条匹配记录:\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r.get('title', 'N/A')}")

    return results


def export_data(collection, output_file=None):
    """导出所有数据"""
    if output_file is None:
        output_file = f"milvus_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    print("\n" + "=" * 50)
    print("导出数据")
    print("=" * 50)

    all_data = []
    batch_size = 1000
    total = collection.num_entities

    print(f"总记录数: {total}")
    print("正在导出...")

    for offset in range(0, total, batch_size):
        results = collection.query(
            expr="id >= 0",
            output_fields=["id", "title", "text", "subject"],
            limit=batch_size,
            offset=offset
        )
        all_data.extend(results)
        progress = min(offset + batch_size, total)
        print(f"  进度: {progress}/{total} ({100*progress/total:.1f}%)")

    # 保存到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "collection": COLLECTION_NAME,
            "export_time": datetime.now().isoformat(),
            "total_records": len(all_data),
            "records": all_data
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 导出完成!")
    print(f"文件: {output_file}")
    print(f"记录数: {len(all_data)}")

    return all_data


def test_retrieval(collection):
    """测试向量检索功能"""
    print("\n" + "=" * 50)
    print("向量检索测试")
    print("=" * 50)
    
    # 获取查询文本
    query_text = input("请输入检索关键词: ").strip()
    if not query_text:
        print("关键词不能为空")
        return
    
    top_k = input("请输入返回数量 (默认5): ").strip()
    top_k = int(top_k) if top_k else 5
    
    # 获取分数阈值
    threshold = input("请输入最低分数阈值 (0-1，默认0.0): ").strip()
    threshold = float(threshold) if threshold else 0.0
    
    print(f"\n正在检索: '{query_text}'...")
    print(f"返回数量: {top_k}, 分数阈值: {threshold}")
    print("-" * 50)
    
    try:
        # 检查集合是否有向量字段
        has_vector = False
        vector_field = None
        for field in collection.schema.fields:
            if field.dtype == 101:  # FloatVector
                has_vector = True
                vector_field = field.name
                break
        
        if not has_vector:
            print("❌ 集合中没有向量字段，无法进行向量检索")
            return
        
        # 提示用户需要使用 embedding 模型
        print("\n⚠️  注意: 直接 Milvus 查询需要预计算的向量。")
        print("建议通过 API 测试向量检索功能：")
        print(f"  curl -X POST http://localhost:8002/retrieval \\")
        print(f"    -H 'Authorization: Bearer your-api-key-here' \\")
        print(f"    -d '{{\"knowledge_id\": \"policy_documents_v3\", \"query\": \"{query_text}\", \"retrieval_setting\": {{ \"top_k\": {top_k}, \"score_threshold\": {threshold} }}}}'")
        
        # 显示集合信息
        print(f"\n集合信息:")
        print(f"  - 集合名: {COLLECTION_NAME}")
        print(f"  - 记录数: {collection.num_entities}")
        print(f"  - 向量字段: {vector_field}")
        
        # 查询相关文档（使用文本搜索作为示例）
        print(f"\n使用文本搜索作为替代演示...")
        results = collection.query(
            expr=f'title like "%{query_text}%" or text like "%{query_text}%"',
            output_fields=["id", "title", "text", "subject"],
            limit=top_k
        )
        
        if results:
            print(f"\n找到 {len(results)} 条相关记录:\n")
            for i, r in enumerate(results, 1):
                title = r.get('title', 'N/A')
                subject = r.get('subject', 'N/A')
                text = r.get('text', '')[:150]
                
                print(f"[{i}] {title}")
                print(f"    Subject: {subject}")
                print(f"    Text: {text}...")
                print()
        else:
            print("未找到匹配的记录")
        
    except Exception as e:
        print(f"❌ 检索失败: {e}")


def delete_all_data(collection):
    """删除所有数据（危险操作）"""
    print("\n" + "=" * 50)
    print("⚠️  删除所有数据")
    print("=" * 50)

    confirm = input("确定要删除所有数据吗? (输入 'YES' 确认): ")
    if confirm != "YES":
        print("取消删除操作")
        return

    result = collection.delete("id >= 0")
    collection.flush()
    print(f"\n✅ 删除完成! 删除记录数: {result.delete_count}")


def main():
    """主函数"""
    print("=" * 50)
    print("Milvus 数据库测试工具")
    print("=" * 50)

    try:
        collection = connect_milvus()
        collection.load()

        while True:
            print("\n" + "-" * 50)
            print("请选择操作:")
            print("1. 查看集合信息")
            print("2. 查询所有数据")
            print("3. 按标题查询")
            print("4. 文本搜索")
            print("5. 导出所有数据")
            print("6. 检索测试")
            print("7. 删除所有数据 (危险)")
            print("0. 退出")
            print("-" * 50)

            choice = input("\n请输入选项: ").strip()

            if choice == "1":
                get_collection_info(collection)

            elif choice == "2":
                limit = input("请输入查询数量 (默认10): ").strip()
                limit = int(limit) if limit else 10
                query_all(collection, limit)

            elif choice == "3":
                title = input("请输入标题: ").strip()
                if title:
                    query_by_title(collection, title)

            elif choice == "4":
                keyword = input("请输入搜索关键词: ").strip()
                if keyword:
                    limit = input("请输入返回数量 (默认10): ").strip()
                    limit = int(limit) if limit else 10
                    search_by_text(collection, keyword, limit)

            elif choice == "5":
                export_data(collection)

            elif choice == "6":
                test_retrieval(collection)

            elif choice == "7":
                delete_all_data(collection)
                collection.release()
                collection.load()

            elif choice == "0":
                print("\n感谢使用!")
                break

            else:
                print("无效选项")

    except Exception as e:
        print(f"\n❌ 错误: {e}")

    finally:
        connections.disconnect(alias="default")
        print("\n已断开Milvus连接")


if __name__ == "__main__":
    main()
