"""
远程 Reranker 服务 - 调用远程 Reranker API 进行文档重排序
"""

import logging
from typing import List

import requests

from core.config import settings

logger = logging.getLogger(__name__)


class RemoteRerankerService:
    """远程 Reranker 服务类"""

    def __init__(self):
        """初始化远程 Reranker 服务"""
        self.api_url = settings.reranker_api_url
        self.timeout = settings.reranker_timeout

        if not self.api_url:
            raise ValueError("reranker_api_url 未配置")

        logger.info(f"初始化远程 Reranker 服务: {self.api_url}")

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: int | None = None,
    ) -> List[float]:
        """
        调用远程 Reranker API 对文档进行重排序

        Args:
            query: 查询文本
            documents: 待排序的文档列表
            top_n: 返回前 N 个结果（可选）

        Returns:
            List[float]: 每个文档的相关性分数（顺序与输入 documents 一致）
        """
        if not documents:
            return []

        try:
            # 构建请求
            # max_tokens_per_doc=480: 每个文档最多 480 tokens
            # 留有余量，确保 query+doc 不超过 512 限制
            payload = {
                "query": query,
                "documents": documents,
                "max_tokens_per_doc": 480,
            }

            if top_n is not None:
                payload["top_n"] = top_n

            # 发送请求
            response = requests.post(
                f"{self.api_url}/rerank",
                json=payload,
                timeout=self.timeout,
            )

            response.raise_for_status()
            result = response.json()

            # 解析结果
            # 远程 API 返回的 results 是按分数排序的，我们需要按原始索引恢复顺序
            scores = [0.0] * len(documents)
            for item in result.get("results", []):
                index = item.get("index", 0)
                score = item.get("relevance_score", 0.0)
                if 0 <= index < len(documents):
                    scores[index] = float(score)

            logger.info(
                f"远程 Rerank 完成: query='{query[:30]}...', "
                f"docs={len(documents)}, top_n={top_n}"
            )

            return scores

        except requests.exceptions.Timeout:
            logger.error(f"远程 Rerank 超时: {self.timeout}s")
            raise TimeoutError(f"Rerank 请求超时（{self.timeout}s）")

        except requests.exceptions.RequestException as e:
            logger.error(f"远程 Rerank 请求失败: {e}")
            raise ConnectionError(f"Rerank 服务连接失败: {e}")

        except Exception as e:
            logger.error(f"远程 Rerank 异常: {e}")
            raise
