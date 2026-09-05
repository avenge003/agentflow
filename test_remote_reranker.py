#!/usr/bin/env python3
"""测试远程 Reranker API 的性能"""

import requests
import time
import json

API_URL = "http://192.168.3.6:8001/rerank"

def test_remote_reranker_speed():
    """测试远程 Reranker 的性能"""
    print("=" * 70)
    print("远程 Reranker API 性能测试")
    print("=" * 70)
    print(f"API 地址: {API_URL}")

    # 测试用例
    test_cases = [
        {
            "name": "少量文档 (5条)",
            "query": "社保政策办理流程",
            "documents": [
                "办理社保需要准备身份证、户口本等材料",
                "厂房设施管理规程要求定期检查设备",
                "人事管理岗位职责包括招聘和培训",
                "住房公积金提取条件和流程说明",
                "医疗保险报销比例和范围介绍",
            ],
        },
        {
            "name": "中等文档 (10条)",
            "query": "社保政策办理流程",
            "documents": [
                "办理社保需要准备身份证、户口本等材料",
                "厂房设施管理规程要求定期检查设备",
                "人事管理岗位职责包括招聘和培训",
                "住房公积金提取条件和流程说明",
                "医疗保险报销比例和范围介绍",
                "失业保险金领取条件和标准",
                "生育保险待遇申请流程",
                "工伤认定标准和赔偿标准",
                "养老保险缴费基数和比例",
                "社保转移接续办理流程",
            ],
        },
        {
            "name": "大量文档 (20条)",
            "query": "社保政策办理流程",
            "documents": [
                "办理社保需要准备身份证、户口本等材料",
                "厂房设施管理规程要求定期检查设备",
                "人事管理岗位职责包括招聘和培训",
                "住房公积金提取条件和流程说明",
                "医疗保险报销比例和范围介绍",
                "失业保险金领取条件和标准",
                "生育保险待遇申请流程",
                "工伤认定标准和赔偿标准",
                "养老保险缴费基数和比例",
                "社保转移接续办理流程",
                "社保卡办理流程和所需材料",
                "社保缴费查询方法",
                "社保待遇资格认证",
                "社保关系转移申请",
                "社保基金监督管理办法",
                "社保经办机构职责",
                "社保信息系统建设",
                "社保档案管理规定",
                "社保统计报告制度",
                "社保稽核检查工作",
            ],
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
                    json={
                        "query": test_case["query"],
                        "documents": test_case["documents"],
                        "top_n": len(test_case["documents"]),
                    },
                    timeout=30,
                )

                end_time = time.time()
                elapsed = (end_time - start_time) * 1000  # 转换为毫秒
                times.append(elapsed)

                if j == 0:  # 第一次打印详细信息
                    if response.status_code == 200:
                        data = response.json()
                        print(f"  ✓ 状态: {response.status_code}")
                        print(f"  ✓ 返回结果数: {len(data.get('results', []))}")
                        if data.get("results"):
                            top_result = data["results"][0]
                            print(f"  ✓ 最高分: {top_result['relevance_score']:.4f}")
                    else:
                        print(f"  ✗ 错误: {response.status_code}")
                        print(f"  ✗ 响应: {response.text[:200]}")

            except requests.exceptions.Timeout:
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
            "doc_count": len(test_case["documents"]),
            "avg_time": avg_time,
            "min_time": min_time,
            "max_time": max_time,
        })

    # 总结
    print("\n" + "=" * 70)
    print("远程 Reranker 性能总结")
    print("=" * 70)
    print(f"\n{'测试名称':<30} {'文档数':<10} {'平均耗时':<15} {'最快':<12} {'最慢':<12}")
    print("-" * 70)

    for result in results:
        print(f"{result['name']:<30} {result['doc_count']:>8}条 {result['avg_time']:>10.0f}ms {result['min_time']:>10.0f}ms {result['max_time']:>10.0f}ms")

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

    # 与本地模型对比
    print("\n" + "=" * 70)
    print("与本地模型对比")
    print("=" * 70)
    local_time = 2163  # 本地模型 20 个文档的耗时
    remote_time = results[2]["avg_time"]  # 远程模型 20 个文档的耗时

    if local_time > 0 and remote_time > 0:
        improvement = ((local_time - remote_time) / local_time) * 100
        print(f"\n文档数: 20")
        print(f"本地模型: {local_time:.0f}ms")
        print(f"远程模型: {remote_time:.0f}ms")
        print(f"性能提升: {improvement:.1f}%")
        print(f"加速倍数: {local_time/remote_time:.1f}x")


if __name__ == "__main__":
    test_remote_reranker_speed()
