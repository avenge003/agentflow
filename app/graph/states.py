from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_message

class InputState(TypedDict):
    """
    输入状态
    """
    user_input: str

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
    sql_analysis_result: str
    other_results: str
    messages: Annotated[list, add_message]
