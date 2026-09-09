from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages
from operator import add

class InputState(TypedDict):
    """
    输入状态
    """
    user_input: str
    messages: list  # 历史会话上下文（压缩摘要 + 压缩点之后的会话内容）

class UserInputClassification(TypedDict):
    """
    用户输入分类
    """
    classification: Literal["rag", "sql", "other"]
    user_input: str

class QueryMilvusState(TypedDict):
    """
    查询Milvus状态
    """
    user_input: str

class UserInputSplit(TypedDict):
    """
    用户输入拆分
    """
    user_input_real: str
    user_inputs: list[str]

class OverAllState(TypedDict):
    """
    系统状态
    """
    user_input: str
    classification: UserInputClassification
    user_input_split: UserInputSplit
    milvus_results: Annotated[list[str], add]
    sql_str: str
    sql_results: list[tuple]
    sql_retry_count: int   # SQL 执行失败次数（用于限制重试轮数）
    sql_error: str         # 最近一次 SQL 执行错误信息（为空表示执行成功）
    sql_analysis_result: str
    other_results: str
    rag_result: str
    messages: Annotated[list, add_messages]
