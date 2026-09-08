from pathlib import Path
from typing import TypedDict, Literal, Annotated
from operator import add

from langchain.messages import HumanMessage, SystemMessage
from app.services.model_service import ModelService
from app.services.milvus_service import MilvusService

from .states import OverAllState, InputState, UserInputClassification, UserInputSplit, QueryMilvusState

model_service = ModelService()
milvus_service = MilvusService()
milvus_service.connect()
model = model_service.load_llm_model()


def load_prompt(name: str) -> str:
    """
    加载提示模板
    Args:
        name: 提示模板名称
    Returns:
        str: 提示模板内容
    """
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{name}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(f"提示模板文件不存在: {prompt_path}")


def classify_user_input(state: InputState) -> OverAllState:
    """
    对用户输入进行分类
    """
    user_input = state["user_input"]
    system_content = load_prompt("classifier")

    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=user_input)
    messages = [system_message, human_message]
    
    response = model.with_structured_output(UserInputClassification).invoke(messages)

    return {
        "user_input": user_input,
        "classification": response["classification"],
        "messages": [response]
    }

def split_user_input(state: OverAllState) -> OverAllState:
    """
    对用户输入进行拆分
    """
    user_input = state["user_input"]
    system_content = load_prompt("spliter")
    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=user_input)
    messages = [system_message, human_message]
    
    user_input_split = model.with_structured_output(UserInputSplit).invoke(messages)

    return {
        "user_input_split": user_input_split,
        "messages": [response]
    }



def query_milvus(state: QueryMilvusState) -> OverAllState:
    """
    查询Milvus
    """
    user_input = state["user_input"]
    # query_embedding = embedding_service.encode_query(user_input)
    # 从Milvus中查询
    # milvus_results = milvus_service.hybrid_search(
    #     query_text=user_input,
    #     query_embedding=query_embedding,
    #     top_k=recall_top_k
    # )

    milvus_results = f"{user_input}的查询结果。"

    return {
        "milvus_results": [milvus_results]
    }

def sql_generator(state: OverAllState) -> OverAllState:
    """
    生成SQL查询语句
    """
    user_input = state["user_input"]
    system_content = load_prompt("sqlgenerator")
    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=user_input)
    messages = [system_message, human_message]
    
    response = model.invoke(messages)

    return {
        "sql_str": response.content.replace("```sql", "").replace("```", ""),
        "messages": [response]
    }

def sql_executor(state: OverAllState) -> OverAllState:
    """
    执行SQL查询语句
    """
    sql_str = state["sql_str"]
    sql_results = []
    # 连接数据库，执行SQL查询语句
    conn = pymssql.connect(
        server='208.208.0.252',
        user='sa',
        password='etc12+mdx',
        database='ytzy',
        port=1433,
        tds_version='7.0',  # <--- 关键修改：尝试指定版本
        charset='UTF-8')
    cursor = conn.cursor()
    cursor.execute(sql_str)
    for row in cursor.fetchall():
        sql_results.append(row)
    conn.close()

    return {
        "sql_results": sql_results
    }

def sql_analyzer(state: OverAllState) -> OverAllState:
    """
    分析SQL查询结果
    """
    sql_results = state["sql_results"]
    user_input = state["user_input"]

    # 分析SQL查询结果

    system_content = load_prompt("dataanalyzer")
    user_content=f"""
        用户的输入内容：{user_input}
        用户查询到的业务数据如下：
        {sql_results}
    """
    
    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=user_content)
    messages = [system_message, human_message]
    response = model.invoke(messages)
    sql_analysis_result = response.content

    return {
        "sql_analysis_result": sql_analysis_result,
        "messages": [response]
    }

def other_agent(state: OverAllState) -> OverAllState:
    """
    其他查询
    """
    user_input = state["user_input"]
    result = model.invoke([HumanMessage(content=user_input)])
    return {
        "other_results": result.content,
        "messages": [result]
    }


