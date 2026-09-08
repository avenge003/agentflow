"""FastAPI主应用入口"""

import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import documents
from app.core.config import settings
from app.services.milvus_service import MilvusService
from app.services.model_service import ModelService
from app.services.reranker_service import RemoteRerankerService
from app.services.embedding_service import RemoteEmbeddingService

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局服务实例
milvus_service = MilvusService()
model_service = ModelService()
reranker_service = None
embedding_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件
    logger.info("应用启动中...")

    # 1. 初始化Milvus连接
    logger.info("正在初始化Milvus连接...")
    milvus_service.connect()

    # 2. 创建集合
    logger.info("正在创建/加载Milvus集合...")
    milvus_service.create_collection()

    # 3. 加载 Embedding（远程或本地）
    global embedding_service
    if settings.use_remote_embedding and settings.embedding_api_url:
        logger.info("使用远程 Embedding 服务，跳过本地 Embedding 模型加载")
        logger.info(f"远程 Embedding 地址: {settings.embedding_api_url}")

        # 初始化远程 Embedding 服务
        try:
            embedding_service = RemoteEmbeddingService()
            logger.info("远程 Embedding 服务初始化成功")
        except Exception as e:
            logger.error(f"远程 Embedding 服务初始化失败: {e}")
            logger.warning("回退到本地 Embedding 模型")
            model_service.load_embedding_model()
            embedding_service = None
    else:
        logger.info("使用本地 Embedding 模型")
        model_service.load_embedding_model()
        embedding_service = None

    # 4. 加载本地 Reranker 模型（仅在不使用远程服务时）
    global reranker_service
    if settings.use_remote_reranker and settings.reranker_api_url:
        logger.info("使用远程 Reranker 服务，跳过本地 Reranker 模型加载")
        logger.info(f"远程 Reranker 地址: {settings.reranker_api_url}")

        # 初始化远程 Reranker 服务
        try:
            reranker_service = RemoteRerankerService()
            logger.info("远程 Reranker 服务初始化成功")
        except Exception as e:
            logger.error(f"远程 Reranker 服务初始化失败: {e}")
            logger.warning("回退到本地 Reranker 模型")
            model_service.load_reranker_model()
            reranker_service = None
    else:
        logger.info("使用本地 Reranker 模型")
        model_service.load_reranker_model()
        reranker_service = None

    # 5. 设置服务实例到路由模块
    documents.set_services(milvus_service, model_service, reranker_service, embedding_service)

    logger.info("应用启动完成")

    yield

    # 关闭事件
    logger.info("应用关闭中...")
    milvus_service.close()
    logger.info("应用已关闭")


# 创建FastAPI应用实例
app = FastAPI(
    title=settings.app_name,
    description="基于本地化模型的RAG文档检索API服务，支持混合检索（BM25+向量）和reranker重排序",
    version=settings.app_version,
    lifespan=lifespan,
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(documents.router)
