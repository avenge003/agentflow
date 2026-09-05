from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API配置
    app_name: str = "RagFlow API"
    app_version: str = "1.1.0"  # G7/G1/G3 改造后版本号
    debug: bool = False

    # Milvus配置
    milvus_host: str = "192.168.3.195"
    milvus_port: int = 19530
    milvus_user: str = "root"
    milvus_password: str = "Milvus"
    # G7: 默认集合统一为 policy_documents（与 test.py 一致）
    milvus_collection_name: str = "policy_documents"
    # G7: 灰度切流用的 alias（默认 alias 指向当前主集合）
    milvus_collection_alias: str = "default"
    # G7: 是否启用新 schema（subject 纯字符串 + file_path 独立字段）
    enable_v2_schema: bool = True

    # 模型配置
    embedding_model_path: str = "./models/embedding/bge-large-zh-v1.5"
    reranker_model_path: str = "./models/reranker/bge-reranker-base"
    embedding_dimension: int = 1024
    use_fp16: bool = True

    # 远程 Reranker 服务配置
    reranker_api_url: str = ""  # 例如: "http://192.168.3.6:8001"
    reranker_timeout: int = 30  # 请求超时时间（秒）
    use_remote_reranker: bool = True  # 是否使用远程 Reranker

    # 远程 Embedding 服务配置
    embedding_api_url: str = ""  # 例如: "http://192.168.3.6:8002"
    embedding_timeout: int = 30  # 请求超时时间（秒）
    use_remote_embedding: bool = True  # 是否使用远程 Embedding

    # API Key认证配置
    api_keys: str = "your-api-key-here"

    # 检索配置
    default_top_k: int = 10
    default_score_threshold: float = 0.0
    bm25_weight: float = 0.5
    vector_weight: float = 0.5

    # G1: 混合检索（Milvus Hybrid Search + RRF）参数
    enable_hybrid: bool = True
    hybrid_dense_limit: int = 20  # 单路（dense）召回数
    hybrid_sparse_limit: int = 20  # 单路（sparse_bm25）召回数
    rrf_k: int = 60  # Reciprocal Rank Fusion 的常数 k

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
