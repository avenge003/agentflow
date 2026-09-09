"""文档相关 API 路由

Phase 1 改造要点（v1.1.0）：
  - G7: store/update 写入时显式携带 file_path；不再"占位" 0 向量
  - G1: /retrieval 改调 hybrid_search，传入 query 原文
  - G3: update 接口不再本地构造 [0.0]*1024 占位向量
"""

import asyncio
import json
import logging
import uuid

import numpy as np
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain.messages import AIMessage, HumanMessage
from langchain_core.callbacks import BaseCallbackHandler

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
)
from app.services.milvus_service import MilvusService
from app.services.model_service import ModelService
from app.services.reranker_service import RemoteRerankerService
from app.services.embedding_service import RemoteEmbeddingService
from app.graph.builder import build_graph
from app.graph.nodes import model as agent_llm

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


# ==================== 会话历史与自动压缩 ====================
# 内存会话存储: {session_id: {"summary": str | None, "messages": [{"role", "content"}]}}
# summary 为压缩摘要（压缩点之前的内容）；messages 为压缩点之后的会话内容
_session_histories: dict[str, dict] = {}


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数：中文约 1 字 1 token，其他字符约 4 字符 1 token"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + (len(text) - cjk) // 4 + 1


def _get_session(session_id: str) -> dict:
    if session_id not in _session_histories:
        _session_histories[session_id] = {"summary": None, "messages": []}
    return _session_histories[session_id]


def _context_token_count(store: dict) -> int:
    """当前上下文量：压缩摘要 + 压缩点之后的会话内容（估算 tokens）"""
    total = _estimate_tokens(store.get("summary") or "")
    total += sum(_estimate_tokens(m["content"]) for m in store["messages"])
    return total


def _extract_usage(message) -> dict | None:
    """从 AIMessage 提取真实 token 用量，兼容不同 langchain 版本 / 提供商字段"""
    usage = getattr(message, "usage_metadata", None)
    if usage:
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
    meta = getattr(message, "response_metadata", None) or {}
    token_usage = meta.get("token_usage") or meta.get("usage")
    if token_usage:
        inp = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0))
        out = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0))
        return {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": token_usage.get("total_tokens", inp + out),
        }
    return None


class UsageStatsHandler(BaseCallbackHandler):
    """累计一次运行中所有 LLM 调用的 token 用量（图内各节点 + 压缩调用统一经回调埋点）。

    优先取提供商返回的真实 usage；拿不到时用 _estimate_tokens 估算兜底，
    并计入 estimated_calls，便于区分统计口径。
    """

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.calls = 0
        self.estimated_calls = 0
        self._est_pending = 0
        self._seen_run_ids: set = set()

    def on_chat_model_start(self, serialized, messages, **kwargs):  # noqa: ANN001
        if kwargs.get("run_id") in self._seen_run_ids:
            return
        try:
            self._est_pending = sum(
                _estimate_tokens(getattr(m, "content", "") or "")
                for batch in messages
                for m in batch
            )
        except Exception:
            self._est_pending = 0

    # langchain_core 新版结束事件为 on_llm_end（LLMResult），
    # 旧版/部分模型为 on_chat_model_end；两者都挂，用 run_id 去重
    def on_llm_end(self, response, **kwargs):  # noqa: ANN001
        self._handle_end(response, **kwargs)

    def on_chat_model_end(self, response, **kwargs):  # noqa: ANN001
        self._handle_end(response, **kwargs)

    def _handle_end(self, response, **kwargs):  # noqa: ANN001
        run_id = kwargs.get("run_id")
        if run_id is not None:
            if run_id in self._seen_run_ids:
                return
            self._seen_run_ids.add(run_id)
        self.calls += 1
        try:
            # response 可能是 LLMResult（标准回调）、AIMessage/AIMessageChunk
            message = None
            if hasattr(response, "content"):
                message = response
            elif getattr(response, "generations", None):
                message = response.generations[0][0].message
            elif getattr(response, "message", None) is not None:
                message = response.message
            usage = _extract_usage(message) if message is not None else None
            if usage and (usage["input_tokens"] or usage["output_tokens"]):
                self.input_tokens += usage["input_tokens"]
                self.output_tokens += usage["output_tokens"]
                self.total_tokens += usage["total_tokens"] or usage["input_tokens"] + usage["output_tokens"]
            else:
                # 估算兜底：输入用 start 时统计值，输出按回复内容估算
                self.estimated_calls += 1
                output = _estimate_tokens(getattr(message, "content", "") or "")
                self.input_tokens += self._est_pending
                self.output_tokens += output
                self.total_tokens += self._est_pending + output
        except Exception as e:
            logger.warning(f"统计 token 用量失败: {e}")
        finally:
            self._est_pending = 0

    def snapshot(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
            "estimated_calls": self.estimated_calls,
        }


_COMPRESS_PROMPT = """你是对话历史压缩器。请将【已有摘要】与【待压缩对话】整合为一份新的简洁摘要，作为后续对话的上下文。
要求：
1. 保留关键实体、业务数据、结论以及用户未完成的需求；
2. 去除寒暄与重复内容；
3. 使用中文，控制在 500 字以内，直接输出摘要正文。

【已有摘要】
{prev_summary}

【待压缩对话】
{transcript}"""


def _compress_history(store: dict, handler: "UsageStatsHandler | None" = None) -> None:
    """超过阈值时自动压缩历史：
    以压缩点为界，将旧摘要 + 压缩点前更早的消息合并为新摘要，
    仅保留最近 compress_keep_recent 条消息在压缩点之后。
    """
    threshold = int(settings.context_max_tokens * settings.compress_threshold)
    keep = max(settings.compress_keep_recent, 1)

    total = _context_token_count(store)
    if total <= threshold or len(store["messages"]) <= keep:
        return  # 未超阈值，或压缩点之后已无可再压缩的消息

    older = store["messages"][:-keep]
    recent = store["messages"][-keep:]
    transcript = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}" for m in older
    )
    prompt = _COMPRESS_PROMPT.format(
        prev_summary=store.get("summary") or "（无）",
        transcript=transcript,
    )
    try:
        cfg = {"callbacks": [handler]} if handler is not None else None
        resp = agent_llm.invoke([HumanMessage(content=prompt)], config=cfg)
        store["summary"] = resp.content
        store["messages"] = recent  # 更新压缩点
        logger.info(
            f"会话历史已压缩: 估算 {total} tokens 超过阈值 {threshold}，"
            f"新摘要 {len(store['summary'])} 字，压缩点后保留 {len(recent)} 条消息"
        )
    except Exception as e:
        logger.error(f"压缩会话历史失败: {e}", exc_info=True)


def _build_history_payload(store: dict) -> list:
    """组装调用上下文：压缩摘要 + 压缩点之后的会话内容（不含本轮输入）"""
    msgs: list = []
    if store.get("summary"):
        msgs.append(HumanMessage(content=f"【历史会话摘要】\n{store['summary']}"))
    for m in store["messages"][:-1]:  # 末条为本轮输入，经 user_input 传入
        if m["role"] == "user":
            msgs.append(HumanMessage(content=m["content"]))
        else:
            msgs.append(AIMessage(content=m["content"]))
    return msgs


# ==================== Agent Chat ====================
@router.post(
    "/agent/chat",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def agent_chat(
    request: AgentChatRequest,
    # api_key: str = Depends(verify_api_key),
) -> StreamingResponse:
    """Agent Chat 接口（流式 SSE 输出）

    - stream_mode="messages" 逐 token 推送终止节点（sql_analyzer / rag_agent / other_agent / sql_fallback）的回答，
      中间节点（分类、SQL 生成等）的输出不推送给客户端。
    - 会话保持：thread_id 作为会话键；历史超过阈值时自动压缩，
      调用时上下文 = 压缩摘要 + 压缩点之后的会话内容。
    - 结束事件 meta 中返回：tokens_used（本次请求 LLM 消耗 token）、
      context_limit（上下文上限）、context_current（当前上下文量，估算 tokens）。
    """
    user_input = request.user_input
    session_id = request.thread_id or uuid.uuid4().hex
    graph = build_graph()

    # 1) 记录本轮用户输入，2) 超阈值则自动压缩，3) 组装上下文
    store = _get_session(session_id)
    store["messages"].append({"role": "user", "content": user_input})
    usage_handler = UsageStatsHandler()  # 统一埋点：压缩调用 + 图内所有 LLM 调用
    await asyncio.to_thread(_compress_history, store, usage_handler)
    history_msgs = _build_history_payload(store)

    # 仅转发这些终止节点产生的内容
    terminal_nodes = {"sql_analyzer", "rag_agent", "other_agent", "sql_fallback"}

    async def event_stream():
        reply_parts: list[str] = []
        try:
            config = {
                "configurable": {
                    "thread_id": session_id,
                },
                "callbacks": [usage_handler],
            }
            # yield f"data: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"
            async for item in graph.astream(
                {"user_input": user_input, "messages": history_msgs},
                stream_mode="messages",
                config=config
            ):
                # 兼容不同 langgraph 版本：(chunk, metadata) 或单独 chunk
                if isinstance(item, tuple) and len(item) == 2:
                    chunk, metadata = item
                else:
                    chunk, metadata = item, {}

                node = (
                    metadata.get("langgraph_node")
                    or metadata.get("langgraph_node_name")
                    or ""
                )
                if node not in terminal_nodes:
                    continue

                content = getattr(chunk, "content", None)
                if not content:
                    continue
                if not isinstance(content, str):
                    content = str(content)
                reply_parts.append(content)
                yield f"data: {json.dumps({'response': content}, ensure_ascii=False)}\n\n"
            # 4) 记录本轮助手回复到压缩点之后的历史
            reply = "".join(reply_parts)
            if reply:
                store["messages"].append({"role": "assistant", "content": reply})
            # 5) 返回本轮 token 用量、上下文上限、当前上下文量
            tokens_used = usage_handler.snapshot()
            context_current = _context_token_count(store)
            logger.info(
                f"会话 {session_id} 本轮 token 用量: total={tokens_used['total_tokens']} "
                f"(calls={tokens_used['calls']}, 估算={tokens_used['estimated_calls']}); "
                f"当前上下文 {context_current}/{settings.context_max_tokens} tokens"
            )
            yield f"data: {json.dumps({'meta': {'tokens_used': tokens_used, 'context_limit': settings.context_max_tokens, 'context_current': context_current}}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Agent 流式输出失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
