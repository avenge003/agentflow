#!/usr/bin/env python3
"""测试 Retrieval API 响应速度"""

import requests
import time
import json
from datetime import datetime

API_URL = "http://localhost:8002/retrieval"
API_KEY = "your-api-key-here"

def test_retrieval_speed():
    """测试检索 API 速度"""
    print("=" * 70)
    print("Retrieval API 响应速度测试")
    print("=" * 70)

    # 测试用例
    test_cases = [
        {
            "name": "快速检索 (top_k=1)",
            "params": {
                "knowledge_id": "test-knowledge",
                "query": "社保政策",
                "retrieval_setting": {
                    "top_k": 1,
                    "score_threshold": 0.5
                }
            }
        },
        {
            "name": "标准检索 (top_k=5)",
            "params": {
                "knowledge_id": "test-knowledge",
                "query": "社保政策",
                "retrieval_setting": {
                    "top_k": 5,
                    "score_threshold": 0.5
                }
            }
        },
        {
            "name": "大量检索 (top_k=10)",
            "params": {
                "knowledge_id": "test-knowledge",
                "query": "社保政策",
                "retrieval_setting": {
                    "top_k": 10,
                    "score_threshold": 0.0
                }
            }
        },
        {
            "name": "通用查询 (top_k=5)",
            "params": {
                "knowledge_id": "test-knowledge",
                "query": "厂房设施管理",
                "retrieval_setting": {
                    "top_k": 5,
                    "score_threshold": 0.0
                }
            }
        },
    ]

    # 执行测试
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n【测试 {i}/{len(test_cases)}】{test_case['name']}")
        print("-" * 70)

        # 多次测试取平均值
        times = []
        for j in range(3):
            start_time = time.time()

            try:
                response = requests.post(
                    API_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {API_KEY}"
                    },
                    json=test_case["params"],
                    timeout=30
                )

                end_time = time.time()
                elapsed = (end_time - start_time) * 1000  # 转换为毫秒
                times.append(elapsed)

                if j == 0:  # 第一次打印详细信息
                    if response.status_code == 200:
                        data = response.json()
                        record_count = len(data.get("records", []))
                        print(f"  ✓ 状态: {response.status_code}")
                        print(f"  ✓ 返回记录数: {record_count}")
                        if data.get("records"):
                            print(f"  ✓ 最高分数: {data['records'][0]['score']:.4f}")
                    else:
                        print(f"  ✗ 错误: {response.status_code}")
                        print(f"  ✗ 响应: {response.text[:200]}")

            except requests.Timeout:
                print(f"  ✗ 请求超时 (>30s)")
                times.append(30000)
            except Exception as e:
                print(f"  ✗ 异常: {e}")
                times.append(0)

        # 计算平均值
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n  ⏱️  响应时间:")
        print(f"     - 平均: {avg_time:.0f}ms")
        print(f"     - 最快: {min_time:.0f}ms")
        print(f"     - 最慢: {max_time:.0f}ms")

        results.append({
            "name": test_case["name"],
            "avg_time": avg_time,
            "min_time": min_time,
            "max_time": max_time
        })

    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"\n{'测试名称':<30} {'平均耗时':<15} {'最快':<12} {'最慢':<12}")
    print("-" * 70)

    for result in results:
        print(f"{result['name']:<30} {result['avg_time']:>10.0f}ms {result['min_time']:>10.0f}ms {result['max_time']:>10.0f}ms")

    # 性能评估
    print("\n" + "=" * 70)
    print("性能评估")
    print("=" * 70)

    avg_all = sum(r["avg_time"] for r in results) / len(results)

    if avg_all < 500:
        print(f"✅ 优秀: 平均响应时间 {avg_all:.0f}ms < 500ms")
    elif avg_all < 1000:
        print(f"⚠️  良好: 平均响应时间 {avg_all:.0f}ms (500ms - 1000ms)")
    elif avg_all < 3000:
        print(f"⚠️  一般: 平均响应时间 {avg_all:.0f}ms (1s - 3s)")
    else:
        print(f"❌ 较慢: 平均响应时间 {avg_all:.0f}ms > 3s")

    # Dify 兼容性建议
    print("\n" + "=" * 70)
    print("Dify 兼容性建议")
    print("=" * 70)

    if avg_all < 2000:
        print("✅ 响应速度良好，可以满足 Dify 的超时要求")
    elif avg_all < 5000:
        print("⚠️  响应速度一般，建议优化或调整 Dify 超时设置")
    else:
        print("❌ 响应速度较慢，可能需要优化或增加超时时间")

    print("\n建议措施:")
    print("1. 在 Dify 中调整超时设置 (默认 30s)")
    print("2. 优化 Milvus 查询参数 (减少 top_k)")
    print("3. 使用缓存减少重复查询")
    print("4. 考虑异步处理或流式响应")

if __name__ == "__main__":
    test_retrieval_speed()
