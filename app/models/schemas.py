"""Dify 外部知识库 API 数据模型定义"""

from pydantic import BaseModel, Field


# ==================== 请求模型 ====================

class RetrievalSetting(BaseModel):
    """检索配置"""
    top_k: int = Field(..., description="返回的最大结果数量", ge=1)
    score_threshold: float = Field(..., description="相关性分数阈值", ge=0.0, le=1.0)


class MetadataConditionItem(BaseModel):
    """元数据过滤条件项"""
    name: str = Field(..., description="元数据字段名")
    comparison_operator: str = Field(..., description="比较操作符")
    value: str | float | list[str] | None = Field(None, description="比较值")


class MetadataCondition(BaseModel):
    """元数据过滤条件组合"""
    logical_operator: str | None = Field("and", description="逻辑操作符: and/or")
    conditions: list[MetadataConditionItem] = Field(..., description="条件列表")


class RetrievalRequest(BaseModel):
    """知识检索请求"""
    knowledge_id: str = Field(..., description="知识库唯一标识")
    query: str = Field(..., description="检索查询文本", min_length=1)
    retrieval_setting: RetrievalSetting = Field(..., description="检索配置")
    metadata_condition: MetadataCondition | None = Field(None, description="元数据过滤条件")


class DocumentChunk(BaseModel):
    """文档分块"""
    content: str = Field(..., description="文档内容", min_length=1)
    title: str | None = Field(None, description="文档标题")
    metadata: dict = Field(default_factory=dict, description="文档元数据")
    chunk_id: str | None = Field(None, description="分块ID，用于更新操作")
    file_path: str | None = Field(None, description="源文件路径，用于查看源文件")


class StoreDocumentsRequest(BaseModel):
    """存储文档请求"""
    knowledge_id: str = Field(..., description="知识库唯一标识")
    chunks: list[DocumentChunk] = Field(..., description="文档分块列表", min_length=1)


class UpdateDocumentsRequest(BaseModel):
    """更新文档请求"""
    knowledge_id: str = Field(..., description="知识库唯一标识")
    chunks: list[DocumentChunk] = Field(..., description="文档分块列表", min_length=1)
    revectorize: bool = Field(True, description="是否重新向量化")


class DeleteDocumentsRequest(BaseModel):
    """删除文档请求"""
    knowledge_id: str = Field(..., description="知识库唯一标识")
    chunk_ids: list[str] = Field(..., description="要删除的分块ID列表", min_length=1)


# ==================== 响应模型 ====================

class Record(BaseModel):
    """检索结果记录"""
    content: str = Field(..., description="文档内容")
    score: float = Field(..., description="相关性分数", ge=0.0, le=1.0)
    title: str = Field(..., description="文档标题")
    metadata: dict = Field(default_factory=dict, description="文档元数据")


class RetrievalResponse(BaseModel):
    """知识检索响应"""
    records: list[Record] = Field(default_factory=list, description="检索结果列表")


class StoreDocumentsResponse(BaseModel):
    """存储文档响应"""
    chunk_ids: list[str] = Field(default_factory=list, description="新创建的分块ID列表")


class UpdateDocumentsResponse(BaseModel):
    """更新文档响应"""
    chunk_ids: list[str] = Field(default_factory=list, description="更新的分块ID列表")


class DeleteDocumentsResponse(BaseModel):
    """删除文档响应"""
    chunk_ids: list[str] = Field(default_factory=list, description="已删除的分块ID列表")
    status: str = Field(..., description="删除状态")


class AgentChatRequest(BaseModel):
    """智能体请求"""
    user_input: str = Field(..., description="用户输入")

class AgentChatResponse(BaseModel):
    """智能体响应"""
    response: str = Field(..., description="智能体回复")



# ==================== 错误响应模型 ====================

class ErrorResponse(BaseModel):
    """错误响应"""
    error_code: int = Field(..., description="错误码")
    error_msg: str = Field(..., description="错误信息")
