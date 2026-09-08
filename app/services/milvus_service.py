"""Milvus 数据库服务（pymilvus 3.0 MilvusClient API）

Phase 1 改造要点（v1.1.0）：
  - G7: subject 字段不再 JSON 序列化，新增独立 file_path 字段
  - G1: hybrid_search（Milvus 原生 Hybrid Search + RRFRanker）
  - G3: update_documents 改用 upsert（原子性）

技术栈迁移：
  - 原 ORM API（connections.connect / Collection）将于 pymilvus 3.1 移除
  - 本文件使用 MilvusClient（高层 API）作为前向兼容实现

集合 schema（v2）：
  - id           : INT64, is_primary=True, auto_id=True
  - title        : VARCHAR(256)
  - text         : VARCHAR(65535)
  - vector       : FLOAT_VECTOR(1024) 稠密向量
  - sparse_bm25  : SPARSE_FLOAT_VECTOR 由 BM25 Function 自动生成
  - subject      : VARCHAR(256)   纯字符串
  - file_path    : VARCHAR(1024)
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from pymilvus import (
    AnnSearchRequest,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)
from pymilvus.milvus_client.index import IndexParams

from app.core.config import settings

logger = logging.getLogger(__name__)


# ==================== v2 Schema 工厂（G7）====================


def _build_v2_schema(dim: int) -> CollectionSchema:
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=256),
        # BM25 Function 输入字段必须开启分析器，否则 Milvus 拒绝建集合
        # enable_analyzer=True 让 Milvus 走 analyzer 链做分词（默认 standard）
        FieldSchema(
            name="text",
            dtype=DataType.VARCHAR,
            max_length=65535,
            enable_analyzer=True,
            analyzer_params={"type": "chinese"},  # CJK 友好分词
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
        description="RagFlow policy documents (v2 schema with BM25 + dense + subject/file_path)",
    )


def _build_v2_index_params() -> IndexParams:
    """v2 集合的索引参数"""
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


# ==================== v3 Schema 工厂（S5 v1.4 retrieval 召回优化）====================


def _build_v3_schema(dim: int) -> CollectionSchema:
    """v3 schema：新增 text_with_title 字段，BM25 Function 改吃该字段

    根因（v1.3 评估）：
      短 ID 查询（如 "SMPGW043-3-00 的当前版本号"）BM25 完全匹配不到。
      原 v2 BM25 只吃 text 字段（"目的：建立制水岗位职责..."），
      doc_id 在 title 字段（"SMPGW043-3-00 制水岗位职责"），无法被 BM25 检索。

    修复：
      新增 text_with_title = title + " " + text，BM25 Function 改吃这个新字段。
      短 ID / 中文长标题（如"生产前检查场管理规程"）都能在 BM25 端强匹配。
      v1.4 预期 factual 11 条未命中大幅恢复。
    """
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(
            name="text",
            dtype=DataType.VARCHAR,
            max_length=65535,
            enable_analyzer=True,
            analyzer_params={"type": "chinese"},
        ),
        # v1.4 新增：title + text 拼接，作为 BM25 输入
        FieldSchema(
            name="text_with_title",
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
            input_field_names=["text_with_title"],
            output_field_names=["sparse_bm25"],
        ),
    ]
    return CollectionSchema(
        fields=fields,
        functions=functions,
        description="RagFlow policy documents (v3 schema: BM25 eats title+text)",
    )


def _build_v3_index_params() -> IndexParams:
    """v3 索引参数（与 v2 相同）"""
    return _build_v2_index_params()


# ==================== Milvus 服务类 ====================


class MilvusService:
    """基于 MilvusClient 的集合管理服务"""

    def __init__(self):
        # MilvusClient 支持本地文件（Milvus Lite）或远端 server
        # 拼装 URI：http://{host}:{port}
        uri = f"http://{settings.milvus_host}:{settings.milvus_port}"
        self._client: MilvusClient = MilvusClient(
            uri=uri,
            user=settings.milvus_user or None,
            password=settings.milvus_password or None,
        )
        self._rrf_k = settings.rrf_k
        self._dense_limit = settings.hybrid_dense_limit
        self._sparse_limit = settings.hybrid_sparse_limit
        self._collection = settings.milvus_collection_name
        logger.info(f"MilvusClient 已初始化：uri={uri}")

    @property
    def collection_name(self) -> str:
        return self._collection

    @property
    def client(self) -> MilvusClient:
        return self._client

    # ==================== 连接管理 ====================

    def connect(self) -> None:
        """MilvusClient 在 __init__ 已建立连接；此方法保留以兼容旧调用"""
        logger.info("MilvusClient 已就绪（__init__ 时建立连接）")

    def close(self) -> None:
        """关闭 MilvusClient"""
        try:
            self._client.close()
            logger.info("MilvusClient 已关闭")
        except Exception as e:
            logger.error(f"关闭 MilvusClient 失败: {e}")
            raise

    # ==================== 集合管理 ====================

    def create_collection(self) -> None:
        """加载现有集合；若不存在且启用 v2 schema 则自动创建"""
        try:
            if not self._client.has_collection(self._collection):
                if not settings.enable_v2_schema:
                    raise RuntimeError(
                        f"集合 {self._collection} 不存在，且未启用 v2 schema 自动创建。"
                        "请先在 Milvus 中创建集合。"
                    )
                # v1.4：按 schema 版本（v3 / v2）自动创建
                use_v3 = "_v3" in self._collection or "v3_schema" in self._collection
                schema_name = "v3" if use_v3 else "v2"
                logger.warning(
                    f"集合 {self._collection} 不存在，将按 {schema_name} schema 自动创建"
                )
                if use_v3:
                    self._create_v3_collection()
                else:
                    self._create_v2_collection()

            stats = self._client.get_collection_stats(self._collection)
            logger.info(
                f"集合 {self._collection} 已就绪：row_count={stats.get('row_count', '?')}"
            )
        except Exception as e:
            logger.error(f"加载集合失败: {e}")
            raise

    def _create_v2_collection(self) -> None:
        """按 v2 schema 新建集合 + 索引"""
        schema = _build_v2_schema(settings.embedding_dimension)
        index_params = _build_v2_index_params()
        self._client.create_collection(
            collection_name=self._collection,
            schema=schema,
            index_params=index_params,
        )
        logger.info(f"已按 v2 schema 创建集合 {self._collection} 及索引")

    def _create_v3_collection(self) -> None:
        """按 v3 schema 新建集合 + 索引（v1.4：BM25 改吃 text_with_title）"""
        schema = _build_v3_schema(settings.embedding_dimension)
        index_params = _build_v3_index_params()
        self._client.create_collection(
            collection_name=self._collection,
            schema=schema,
            index_params=index_params,
        )
        logger.info(f"已按 v3 schema 创建集合 {self._collection} 及索引")

    # ==================== 写入（G7 / G3）====================

    @staticmethod
    def _prepare_titles(documents: List[Dict[str, Any]]) -> List[str]:
        """规范化 title，生成不重复的 chunk_ids"""
        titles: List[str] = []
        for i, doc in enumerate(documents):
            title = doc.get("title") or f"chunk_{uuid.uuid4().hex[:12]}"
            if title in titles:
                title = f"{title}_{i}"
            titles.append(title)
        return titles

    @staticmethod
    def _build_row(title: str, doc: Dict[str, Any], use_v3: bool = False) -> Dict[str, Any]:
        """构造单行数据（MilvusClient insert/upsert 格式：行 dict）

        v3 schema 多了 text_with_title 字段（title + " " + text），
        作为 BM25 Function 输入（v1.4 retrieval 召回优化）。
        """
        text = doc.get("content", "")
        row: Dict[str, Any] = {
            "title": title,
            "text": text,
            "vector": doc["vector"],
            "subject": doc.get("subject", "") or "",
            "file_path": doc.get("file_path", "") or "",
            # sparse_bm25 由 BM25 Function 自动生成，不在行中提供
        }
        if use_v3:
            # v1.4：把 title 拼到前面，让 BM25 能强匹配短 ID / 中文长标题
            row["text_with_title"] = f"{title} {text}"
        return row

    def insert_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """插入文档（G7）"""
        try:
            titles = self._prepare_titles(documents)
            use_v3 = "_v3" in self._collection
            rows = [self._build_row(t, d, use_v3=use_v3) for t, d in zip(titles, documents)]

            result = self._client.insert(
                collection_name=self._collection, data=rows
            )
            self._client.flush(self._collection)
            inserted = (
                result.get("insert_count", len(rows))
                if isinstance(result, dict)
                else len(rows)
            )
            logger.info(
                f"成功插入 {inserted} 条文档到集合 {self._collection}"
            )
            return titles
        except Exception as e:
            logger.error(f"插入文档失败: {e}")
            raise

    def update_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """更新文档（G3：upsert 原子性）"""
        try:
            titles = self._prepare_titles(documents)
            use_v3 = "_v3" in self._collection
            rows = [self._build_row(t, d, use_v3=use_v3) for t, d in zip(titles, documents)]

            result = self._client.upsert(
                collection_name=self._collection, data=rows
            )
            self._client.flush(self._collection)

            upsert_count = (
                result.get("upsert_count", len(rows))
                if isinstance(result, dict)
                else len(rows)
            )
            logger.info(
                f"upsert 完成：请求 {len(documents)} 条，实际 {upsert_count} 条"
            )
            return titles
        except Exception as e:
            logger.error(f"更新文档失败: {e}")
            raise

    # ==================== 读取（G5 配套）====================

    def fetch_vectors_by_titles(self, titles: List[str]) -> List[Optional[List[float]]]:
        """按 title 拉取已有向量（G5：revectorize=false 时复用旧向量）"""
        if not titles:
            return []
        try:
            titles_str = ", ".join([f'"{t}"' for t in titles])
            filter_expr = f"title in [{titles_str}]"
            rows = self._client.query(
                collection_name=self._collection,
                filter=filter_expr,
                output_fields=["title", "vector"],
            )
            vec_map = {r["title"]: r["vector"] for r in rows}
            missing = [t for t in titles if t not in vec_map]
            if missing:
                logger.warning(f"fetch_vectors_by_titles：缺失 {len(missing)} 条")
            return [vec_map.get(t) for t in titles]
        except Exception as e:
            logger.error(f"按 title 拉取向量失败: {e}")
            raise

    # ==================== 检索（G1：Hybrid Search + RRF）====================

    def hybrid_search(
        self,
        query_text: str,
        query_embedding: List[float],
        top_k: int = 10,
        filter_expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """混合检索：BM25 稀疏 + 稠密向量，RRF 融合（G1）"""
        try:
            dense_req = AnnSearchRequest(
                data=[query_embedding],
                anns_field="vector",
                param={"metric_type": "IP", "params": {"nprobe": 16}},
                limit=max(self._dense_limit, top_k),
            )
            sparse_req = AnnSearchRequest(
                data=[query_text],
                anns_field="sparse_bm25",
                param={"metric_type": "BM25"},
                limit=max(self._sparse_limit, top_k),
            )
            ranker = RRFRanker(k=self._rrf_k)

            results = self._client.hybrid_search(
                collection_name=self._collection,
                reqs=[sparse_req, dense_req],
                ranker=ranker,
                limit=top_k,
                output_fields=["id", "title", "text", "subject", "file_path"],
                filter=filter_expr,
            )

            formatted: List[Dict[str, Any]] = []
            for hits in results:
                for hit in hits:
                    # MilvusClient 返回的 hit 字段：id, distance, output_fields
                    score = hit.get("distance", hit.get("score", 0.0))
                    formatted.append(
                        {
                            "chunk_id": str(hit.get("id", "")),
                            "title": hit.get("title", ""),
                            "content": hit.get("text", ""),
                            "subject": hit.get("subject", ""),
                            "file_path": hit.get("file_path") or None,
                            "score": float(score),
                        }
                    )

            logger.info(
                f"hybrid_search 完成，返回 {len(formatted)} 条结果 "
                f"(dense_limit={self._dense_limit}, sparse_limit={self._sparse_limit}, rrf_k={self._rrf_k})"
            )
            return formatted
        except Exception as e:
            logger.error(f"混合检索失败: {e}")
            raise

    def search_documents(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        score_threshold: float = 0.0,
        filter_expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """稠密向量单路检索（已弃用：保留供回退 / 评估使用）

        .. deprecated::
            G1 完成后请改用 `hybrid_search`。
        """
        try:
            results = self._client.search(
                collection_name=self._collection,
                data=[query_embedding],
                anns_field="vector",
                limit=top_k,
                output_fields=["id", "title", "text", "subject", "file_path"],
                search_params={"metric_type": "IP", "params": {"nprobe": 16}},
                filter=filter_expr,
            )

            formatted: List[Dict[str, Any]] = []
            for hits in results:
                for hit in hits:
                    score = float(hit.get("distance", hit.get("score", 0.0)))
                    if score < score_threshold:
                        continue
                    formatted.append(
                        {
                            "chunk_id": str(hit.get("id", "")),
                            "title": hit.get("title", ""),
                            "content": hit.get("text", ""),
                            "subject": hit.get("subject", ""),
                            "file_path": hit.get("file_path") or None,
                            "score": score,
                        }
                    )

            logger.info(f"search_documents(单路向量) 完成，返回 {len(formatted)} 条")
            return formatted
        except Exception as e:
            logger.error(f"单路检索失败: {e}")
            raise

    # ==================== 删除（G4 待 Phase 2）====================

    def delete_documents(self, chunk_ids: List[str]) -> Dict[str, int]:
        """删除文档（G4 临时：按 title 批量删除）"""
        try:
            if not chunk_ids:
                logger.warning("未提供要删除的 chunk_ids")
                return {"delete_count": 0}
            titles_str = ", ".join([f'"{t}"' for t in chunk_ids])
            filter_expr = f"title in [{titles_str}]"
            result = self._client.delete(
                collection_name=self._collection, filter=filter_expr
            )
            self._client.flush(self._collection)
            logger.info(
                f"按 title 批量删除 {len(chunk_ids)} 条 from {self._collection}"
            )
            return result if isinstance(result, dict) else {"delete_count": len(chunk_ids)}
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            raise

    # ==================== 统计 ====================

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息"""
        try:
            return self._client.get_collection_stats(self._collection)
        except Exception as e:
            logger.error(f"获取集合统计信息失败: {e}")
            raise
