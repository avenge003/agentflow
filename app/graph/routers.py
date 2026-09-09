from .states import OverAllState, InputState
from .nodes import SQL_MAX_ATTEMPTS
from typing import Sequence, Literal
from langgraph.types import Send

def rag_router(state: OverAllState) -> Sequence[Send]:
    """
    rag_agent路由器
    """
    user_input_split = state["user_input_split"]
    tasks = []
    if user_input_split["user_inputs"]:
        for index, user_input in enumerate(user_input_split["user_inputs"]):
            task = Send(
                "query_milvus",
                {"user_input": user_input},
            )
            tasks.append(task)
    
    return tasks


def classification_router(state: OverAllState) -> Literal["split_user_input", "sql_generator", "other_agent"]:
    """
    分类路由
    """
    classification = state["classification"]
    if classification == "rag":
        return "split_user_input"
    elif classification == "sql":
        return "sql_generator"
    else:
        return "other_agent"


def sql_exec_router(state: OverAllState) -> Literal["sql_analyzer", "sql_generator", "sql_fallback"]:
    """
    SQL 执行结果路由：
      - 执行成功（sql_error 为空）        → sql_analyzer 分析结果
      - 执行失败且未达重试上限           → 回到 sql_generator 带错误信息重新生成
      - 执行失败且已达 SQL_MAX_ATTEMPTS  → sql_fallback 直接输出错误说明
    """
    if not state.get("sql_error"):
        return "sql_analyzer"
    if state.get("sql_retry_count", 0) < SQL_MAX_ATTEMPTS:
        return "sql_generator"
    return "sql_fallback"