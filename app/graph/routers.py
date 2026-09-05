from .state import OverAllState, InputState
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