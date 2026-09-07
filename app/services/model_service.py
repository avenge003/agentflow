"""
本地化模型服务 - 提供向量模型和reranker模型的加载与调用
"""

import logging
import math
from typing import List

import jieba
import numpy as np
import torch
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from langchain.chat_models import init_chat_model
from core.config import settings
from dotenv import load_dotenv
import os
logger = logging.getLogger(__name__)
load_dotenv(override=True, verbose=True)

class ModelService:
    """模型服务类，负责加载和调用embedding和reranker模型"""

    def __init__(self):
        """初始化，从配置读取模型路径和设备信息"""
        self.embedding_model_path = settings.embedding_model_path
        self.reranker_model_path = settings.reranker_model_path
        self.use_fp16 = settings.use_fp16

        # 设备检测
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"使用设备: {self.device}")

        # 模型实例
        self.embedding_model: SentenceTransformer | None = None
        self.reranker_tokenizer = None
        self.reranker_model = None

        # BM25索引
        self.bm25: BM25Okapi | None = None
        self.bm25_corpus: List[List[str]] = []

        self.model_name = settings.model_name
        self.model_provider = settings.model_provider
        self.model_temperature = settings.model_temperature
        self.model_timeout = settings.model_timeout
        self.model_max_retries = settings.model_max_retries
        self.model_base_url = settings.model_base_url
        self.model_api_key = settings.model_api_key

        self.llm_model = None

    def load_llm_model(self):
        """仅加载 llm 模型"""
        if self.llm_model is not None:
            logger.info("LLM 模型已加载，跳过")
            return

        logger.info("开始加载 llm 模型...")
        self.llm_model = init_chat_model(
            self.model_name,
            model_provider=self.model_provider,
            temperature=self.model_temperature,
            timeout=self.model_timeout,
            max_retries=self.model_max_retries,
            base_url=self.model_base_url,
            api_key=self.model_api_key,
            extra_body={
                "thinking": {
                    "type": "disabled"
                    }
            }
        )
        return self.llm_model

    def load_embedding_model(self):
        """仅加载 embedding 模型"""
        if self.embedding_model is not None:
            logger.info("Embedding 模型已加载，跳过")
            return

        logger.info("开始加载 embedding 模型...")
        self.embedding_model = SentenceTransformer(
            self.embedding_model_path,
            device=self.device,
        )
        if self.use_fp16 and self.device == "cuda":
            self.embedding_model.half()
        logger.info(f"Embedding 模型加载完成: {self.embedding_model_path}")

    def load_reranker_model(self):
        """仅加载 reranker 模型"""
        if self.reranker_model is not None:
            logger.info("Reranker 模型已加载，跳过")
            return

        logger.info("开始加载 reranker 模型...")
        self.reranker_tokenizer = AutoTokenizer.from_pretrained(
            self.reranker_model_path,
            use_fast=True,
        )
        self.reranker_model = AutoModelForSequenceClassification.from_pretrained(
            self.reranker_model_path,
        )
        if self.use_fp16 and self.device == "cuda":
            self.reranker_model.half()
        self.reranker_model.to(self.device)
        self.reranker_model.eval()
        logger.info(f"Reranker 模型加载完成: {self.reranker_model_path}")

    def load_models(self):
        """加载 embedding 和 reranker 模型（兼容方法）"""
        self.load_embedding_model()
        self.load_reranker_model()

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        """
        对文本列表进行向量化
        Args:
            texts: 文本列表
        Returns:
            numpy.ndarray: 向量数组
        """
        if not self.embedding_model:
            raise RuntimeError("模型未加载，请先调用 load_models()")

        embeddings = self.embedding_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.array(embeddings)

    def encode_query(self, query: str) -> np.ndarray:
        """
        对查询进行向量化（添加检索指令前缀以优化检索效果）
        Args:
            query: 查询文本
        Returns:
            numpy.ndarray: 查询向量
        """
        if not self.embedding_model:
            raise RuntimeError("模型未加载，请先调用 load_models()")

        # BGE模型需要添加检索指令前缀
        query_with_instruction = f"为这个句子生成表示以用于检索相关文章：{query}"
        embedding = self.embedding_model.encode(
            [query_with_instruction],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.array(embedding)[0]

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """
        对文档列表进行重排序，返回分数列表（0-1范围）
        Args:
            query: 查询文本
            documents: 待排序的文档列表
        Returns:
            list[float]: 每个文档的相关性分数，已通过sigmoid转换到0-1范围
        """
        if not self.reranker_model or not self.reranker_tokenizer:
            raise RuntimeError("reranker模型未加载，请先调用 load_models()")

        if not documents:
            return []

        # 构建输入对
        pairs = [[query, doc] for doc in documents]

        # 编码
        inputs = self.reranker_tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 推理
        with torch.no_grad():
            outputs = self.reranker_model(**inputs)
            scores = outputs.logits.squeeze(-1).cpu().numpy()

        # 通过sigmoid转换为0-1范围
        scores = 1 / (1 + np.exp(-scores))

        return scores.tolist()

    def compute_bm25_sparse(
        self, texts: list[str], query: str
    ) -> dict[int, float]:
        """
        计算BM25稀疏向量表示
        Args:
            texts: 文档文本列表
            query: 查询文本
        Returns:
            dict[int, float]: 文档索引到BM25分数的映射
        """
        if not texts:
            return {}

        # 使用jieba分词
        tokenized_docs = [list(jieba.cut(text)) for text in texts]
        tokenized_query = list(jieba.cut(query))

        # 构建BM25索引
        bm25 = BM25Okapi(tokenized_docs)

        # 计算分数
        scores = bm25.get_scores(tokenized_query)

        # 返回非零分数的索引映射
        result = {}
        for idx, score in enumerate(scores):
            if score > 0:
                result[idx] = float(score)

        return result

    @staticmethod
    def normalize_scores(
        scores: list[float], method: str = "minmax"
    ) -> list[float]:
        """
        归一化分数列表
        Args:
            scores: 原始分数列表
            method: 归一化方法 ('minmax' 或 'softmax')
        Returns:
            list[float]: 归一化后的分数
        """
        if not scores:
            return []

        if method == "minmax":
            min_score = min(scores)
            max_score = max(scores)
            if max_score == min_score:
                return [1.0] * len(scores)
            return [(s - min_score) / (max_score - min_score) for s in scores]

        elif method == "softmax":
            exp_scores = [math.exp(s) for s in scores]
            total = sum(exp_scores)
            return [e / total for e in exp_scores]

        return scores
