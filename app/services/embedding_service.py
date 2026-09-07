"""
远程 Embedding 服务封装
"""

import logging
from typing import List

import requests

from core.config import settings

logger = logging.getLogger(__name__)


class RemoteEmbeddingService:
    """远程 Embedding 服务封装类"""

    def __init__(self):
        """初始化远程 Embedding 服务"""
        self.api_url = settings.embedding_api_url
        self.timeout = settings.embedding_timeout

        if not self.api_url:
            raise ValueError("Embedding API URL 未配置")

        # 确保 URL 格式正确
        if not self.api_url.endswith("/"):
            self.api_url += "/"

        logger.info(f"远程 Embedding 服务初始化成功: {self.api_url}")

    def encode_texts(self, texts: List[str]) -> List[List[float]]:
        """
        调用远程 Embedding API 对文本进行向量化

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 向量列表
        """
        if not texts:
            return []

        try:
            # 构建请求
            payload = {
                "input": texts,
            }

            # 发送请求
            response = requests.post(
                f"{self.api_url}v1/embeddings",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )

            # 检查响应
            if response.status_code != 200:
                error_msg = f"远程 Embedding 请求失败: {response.status_code} {response.text}"
                logger.error(error_msg)
                raise ConnectionError(error_msg)

            # 解析响应
            result = response.json()

            # 提取向量
            embeddings = [item["embedding"] for item in result["data"]]
            logger.debug(f"远程 Embedding 完成: {len(embeddings)} 个向量")

            return embeddings

        except requests.exceptions.Timeout:
            error_msg = "远程 Embedding 请求超时"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"远程 Embedding 请求失败: {e}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

        except Exception as e:
            error_msg = f"远程 Embedding 处理失败: {e}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)

    def encode_query(self, query: str) -> List[float]:
        """
        对单个查询进行向量化

        Args:
            query: 查询文本

        Returns:
            List[float]: 向量
        """
        embeddings = self.encode_texts([query])
        return embeddings[0] if embeddings else []
