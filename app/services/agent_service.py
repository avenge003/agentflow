from typing import TypedDict, Literal, Annotated
from operator import add
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from langchain.messages import HumanMessage, SystemMessage
from app.services.model_service import ModelService
from app.services.milvus_service import MilvusService

model_service = ModelService()
milvus_service = MilvusService()
milvus_service.connect()

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
    milvus_results: Annotated[list[dict], add]


model = model_service.load_llm_model()

def classify_user_input(state: InputState) -> OverAllState:
    """
    对用户输入进行分类
    """
    user_input = state["user_input"]
    system_content = f"""
        你是一个专业的语义分类助手，只能对用户输入进行分类，不能进行其他操作，分类结果只能是rag、sql或other，如果是用户输入的文本是关于药厂制度文件等相关的，分类结果为rag
        如果是用户输入的文本是关于销售采购库存等经营数据相关的，分类结果为sql
        如果是用户输入的文本是关于其他等相关的，分类结果为other
    """
    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=input_content)
    messages = [system_message, human_message]
    
    response = model.with_structured_output(UserInputClassification).invoke(messages)
    return {
        "user_input": user_input,
        "classification": response.classification
    }

def split_user_input(state: OverAllState) -> OverAllState:
    """
    对用户输入进行拆分
    """
    user_input = state["user_input"]
    user_input_split = model.with_structured_output(UserInputSplit).invoke(user_input)
    return {
        "user_input_split": user_input_split
    }

def rag_agent(state: OverAllState) -> OverAllState:
    """
    rag_agent
    """
    user_input_split = state["user_input_split"]

    tasks = []
    if not user_input_split["user_inputs"]:
        for index, user_input in enumerate(user_input_split["user_inputs"]):
            task = Send(
                "query_milvus",
                {"user_input": user_input},
            )
            tasks.append(task)
    
    return tasks

def query_milvus(state: QueryMilvusState) -> OverAllState:
    """
    查询Milvus
    """
    user_input = state["user_input"]
    query_embedding = embedding_service.encode_query(user_input)
    # 从Milvus中查询
    milvus_results = milvus_service.hybrid_search(
                query_text=user_input,
                query_embedding=query_embedding,
                top_k=recall_top_k
            )
    return {
        "milvus_results": milvus_results
    }

def sql_agent(state: OverAllState) -> OverAllState:
    """
    sql_agent
    """
    return state

def other_agent(state: OverAllState) -> OverAllState:
    """
    other_agent
    """
    return state



def classification_router(state: OverAllState) -> Literal["rag_agent", "sql_agent", "other_agent"]:
    """
    分类路由
    """
    classification = state["classification"]
    if classification == "rag":
        return "rag_agent"
    elif classification == "sql":
        return "sql_agent"
    else:
        return "other_agent"

builder = StateGraph(state_schema=OverAllState, input_schema=InputState)
builder.add_node("classify_user_input", classify_user_input)
builder.add_node("rag_agent", rag_agent)
builder.add_node("sql_agent", sql_agent)
builder.add_node("other_agent", other_agent)



builder.add_edge(START, "classify_user_input")
builder.add_conditional_edges("classify_user_input", classification_router)