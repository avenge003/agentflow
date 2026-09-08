"""文档相关 API 路由

Phase 1 改造要点（v1.1.0）：
  - G7: store/update 写入时显式携带 file_path；不再"占位" 0 向量
  - G1: /retrieval 改调 hybrid_search，传入 query 原文
  - G3: update 接口不再本地构造 [0.0]*1024 占位向量
"""

import logging
import uuid

import numpy as np
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.middleware.auth import verify_api_key
from app.models.schemas import (
    DeleteDocumentsRequest,
    DeleteDocumentsResponse,
    ErrorResponse,
    Record,
    RetrievalRequest,
    RetrievalResponse,
    StoreDocumentsRequest,
    StoreDocumentsResponse,
    UpdateDocumentsRequest,
    UpdateDocumentsResponse,
    AgentChatRequest,
    AgentChatResponse,
)
from app.services.milvus_service import MilvusService
from app.services.model_service import ModelService
from app.services.reranker_service import RemoteRerankerService
from app.services.embedding_service import RemoteEmbeddingService
from app.graph.builder import build_graph

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

# 全局服务实例，由 main.py 初始化
milvus_service: MilvusService | None = None
model_service: ModelService | None = None
reranker_service: RemoteRerankerService | None = None
embedding_service: RemoteEmbeddingService | None = None


def set_services(milvus: MilvusService, model: ModelService, reranker: RemoteRerankerService | None = None, embedding: RemoteEmbeddingService | None = None) -> None:
    """设置服务实例"""
    global milvus_service, model_service, reranker_service, embedding_service
    milvus_service = milvus
    model_service = model
    reranker_service = reranker
    embedding_service = embedding


# ==================== 检索（G1）====================


@router.post(
    "/retrieval",
    response_model=RetrievalResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def retrieval(
    request: RetrievalRequest,
    api_key: str = Depends(verify_api_key),
) -> RetrievalResponse:
    """检索文档接口（遵循 Dify API 规范）

    Phase 1 改造：
      - G1: 走 hybrid_search（BM25 + dense，RRF 融合）
      - 旧 search_documents 保留供回退（settings.enable_hybrid=False）
    """
    try:
        logger.info(
            f"收到检索请求: knowledge_id={request.knowledge_id}, "
            f"query={request.query[:50]}..., hybrid={settings.enable_hybrid}"
        )

        # 向量化查询
        # 根据配置选择使用本地还是远程 embedding
        if settings.use_remote_embedding and embedding_service:
            logger.info("使用远程 Embedding 服务")
            query_embedding = embedding_service.encode_query(request.query)
        else:
            logger.info("使用本地 Embedding 模型")
            query_embedding = model_service.encode_query(request.query).tolist()

        # 召回：混合检索 / 单路向量
        # 多召回一些候选给 reranker，留 rerank 余地
        recall_top_k = max(request.retrieval_setting.top_k * 3, 20)
        if settings.enable_hybrid:
            search_results = milvus_service.hybrid_search(
                query_text=request.query,
                query_embedding=query_embedding,
                top_k=recall_top_k,
            )
        else:
            search_results = milvus_service.search_documents(
                query_embedding=query_embedding,
                top_k=recall_top_k,
                score_threshold=0.0,
            )

        if not search_results:
            logger.info("检索结果为空")
            return RetrievalResponse(records=[])

        # rerank 重排
        contents = [r["content"] for r in search_results]

        # 根据配置选择使用本地还是远程 reranker
        if settings.use_remote_reranker and reranker_service:
            logger.info("使用远程 Reranker 服务")
            rerank_scores = reranker_service.rerank(
                request.query,
                contents,
                top_n=len(contents),
            )
        else:
            logger.info("使用本地 Reranker 模型")
            rerank_scores = model_service.rerank(request.query, contents)

        # 应用 score_threshold 过滤 + 构建 records
        records = []
        for result, score in zip(search_results, rerank_scores):
            if score < request.retrieval_setting.score_threshold:
                continue

            subject = result.get("subject", "") or ""
            file_path = result.get("file_path") or None
            metadata: dict = {}
            if subject:
                metadata["subject"] = subject
            if file_path:
                metadata["path"] = file_path

            records.append(
                Record(
                    content=result["content"],
                    score=round(score, 4),
                    title=result.get("title", ""),
                    metadata=metadata,
                )
            )

        # 按 top_k 截断（threshold 已在上一步过滤）
        records = records[: request.retrieval_setting.top_k]

        logger.info(f"检索完成，返回 {len(records)} 条结果")
        return RetrievalResponse(records=records)

    except Exception as e:
        logger.error(f"检索失败: {e}", exc_info=True)
        return ErrorResponse(error_code=500, error_msg=f"检索失败: {str(e)}")


# ==================== 写入（G7）====================


def _build_doc_dict(chunk, vector):
    """构造 Milvus 写入字典（G7：subject/file_path 独立字段）"""
    metadata = chunk.metadata or {}
    subject = metadata.get("subject", metadata.get("source", "")) or ""
    file_path = (
        chunk.file_path
        or metadata.get("file_path")
        or metadata.get("source_path")
        or ""
    )
    return {
        "title": "",  # 由 service 层 _prepare_titles 重新分配
        "content": chunk.content,
        "subject": subject,
        "vector": vector,
        "file_path": file_path,
    }


@router.post(
    "/documents/store",
    response_model=StoreDocumentsResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def store_documents(
    request: StoreDocumentsRequest,
    api_key: str = Depends(verify_api_key),
) -> StoreDocumentsResponse:
    """存储文档接口（G7：向量化 + 独立 file_path 字段）"""
    try:
        logger.info(
            f"收到存储文档请求: knowledge_id={request.knowledge_id}, "
            f"chunks 数量={len(request.chunks)}"
        )

        chunks = request.chunks
        contents = [c.content for c in chunks]

        # 根据配置选择使用本地还是远程 embedding
        if settings.use_remote_embedding and embedding_service:
            logger.info("使用远程 Embedding 服务向量化文档")
            embeddings_list = embedding_service.encode_texts(contents)
            embeddings = np.array(embeddings_list)
        else:
            logger.info("使用本地 Embedding 模型向量化文档")
            embeddings = model_service.encode_texts(contents)

        documents = []
        for i, chunk in enumerate(chunks):
            # 优先用 chunk.title，否则用 chunk.chunk_id
            if chunk.title:
                title = chunk.title
            elif chunk.chunk_id:
                title = chunk.chunk_id
            else:
                title = ""

            doc = _build_doc_dict(chunk, embeddings[i].tolist())
            doc["title"] = title
            documents.append(doc)

        chunk_ids = milvus_service.insert_documents(documents)
        logger.info(f"成功存储 {len(chunk_ids)} 条文档")
        return StoreDocumentsResponse(chunk_ids=chunk_ids)

    except Exception as e:
        logger.error(f"存储文档失败: {e}", exc_info=True)
        return ErrorResponse(error_code=500, error_msg=f"存储文档失败: {str(e)}")


# ==================== 更新（G3 / G5）====================


@router.post(
    "/documents/update",
    response_model=UpdateDocumentsResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def update_documents(
    request: UpdateDocumentsRequest,
    api_key: str = Depends(verify_api_key),
) -> UpdateDocumentsResponse:
    """更新文档接口

    Phase 1 改造：
      - G3: service 层改用 pymilvus.upsert（原子性）
      - G5: 修复 [0.0]*1024 占位向量污染；revectorize=false 时 query 旧向量保留
    """
    try:
        logger.info(
            f"收到更新文档请求: knowledge_id={request.knowledge_id}, "
            f"chunks 数量={len(request.chunks)}, revectorize={request.revectorize}"
        )

        chunks = request.chunks
        documents = []

        if request.revectorize:
            contents = [c.content for c in chunks]

            # 根据配置选择使用本地还是远程 embedding
            if settings.use_remote_embedding and embedding_service:
                logger.info("使用远程 Embedding 服务向量化文档")
                embeddings_list = embedding_service.encode_texts(contents)
                embeddings = np.array(embeddings_list)
            else:
                logger.info("使用本地 Embedding 模型向量化文档")
                embeddings = model_service.encode_texts(contents)

            for i, chunk in enumerate(chunks):
                if chunk.title:
                    title = chunk.title
                elif chunk.chunk_id:
                    title = chunk.chunk_id
                else:
                    title = ""
                doc = _build_doc_dict(chunk, embeddings[i].tolist())
                doc["title"] = title
                documents.append(doc)
        else:
            # G5: 不再本地构造 0 向量；保留旧向量（service 层负责拉取或拒绝）
            titles = []
            for chunk in chunks:
                if chunk.title:
                    titles.append(chunk.title)
                elif chunk.chunk_id:
                    titles.append(chunk.chunk_id)
                else:
                    raise ValueError(
                        "revectorize=false 时必须显式提供 title 或 chunk_id，"
                        "以便 service 层按 title 拉取旧向量"
                    )

            old_vectors = milvus_service.fetch_vectors_by_titles(titles)
            old_map = dict(zip(titles, old_vectors))

            missing = [t for t in titles if not old_map.get(t)]
            if missing:
                # error_code=3001 预留（G5）
                raise ValueError(
                    f"revectorize=false 但下列记录不存在: {missing}"
                )

            for chunk, title in zip(chunks, titles):
                doc = _build_doc_dict(chunk, old_map[title])
                doc["title"] = title
                documents.append(doc)

        chunk_ids = milvus_service.update_documents(documents)
        logger.info(f"成功更新 {len(chunk_ids)} 条文档")
        return UpdateDocumentsResponse(chunk_ids=chunk_ids)

    except Exception as e:
        logger.error(f"更新文档失败: {e}", exc_info=True)
        return ErrorResponse(error_code=500, error_msg=f"更新文档失败: {str(e)}")


# ==================== 删除（G4 待 Phase 2）====================


@router.post(
    "/documents/delete",
    response_model=DeleteDocumentsResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def delete_documents(
    request: DeleteDocumentsRequest,
    api_key: str = Depends(verify_api_key),
) -> DeleteDocumentsResponse:
    """删除文档接口（G4 临时：统一按 title 删除）"""
    try:
        logger.info(
            f"收到删除文档请求: knowledge_id={request.knowledge_id}, "
            f"chunk_ids 数量={len(request.chunk_ids)}"
        )

        chunk_ids = request.chunk_ids
        milvus_service.delete_documents(chunk_ids)
        logger.info(f"成功删除 {len(chunk_ids)} 条文档")
        return DeleteDocumentsResponse(chunk_ids=chunk_ids, status="success")

    except Exception as e:
        logger.error(f"删除文档失败: {e}", exc_info=True)
        return ErrorResponse(error_code=500, error_msg=f"删除文档失败: {str(e)}")


# ==================== Agent Chat ====================
@router.post(
    "/agent/chat",
    response_model=AgentChatResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def agent_chat(
    request: AgentChatRequest,
    api_key: str = Depends(verify_api_key),
) -> AgentChatResponse:
    """Agent Chat 接口"""
    user_input = request.user_input
    graph = build_graph()
    final_state = None
    async for state,metadata in graph.astream(
        {"user_input": user_input},
        stream_mode="messages"
        ):
        final_state = state.content
    return AgentChatResponse(response=final_state)
