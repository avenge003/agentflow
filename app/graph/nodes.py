from pathlib import Path
from typing import TypedDict, Literal, Annotated
from operator import add
import logging
import re

import pymssql
from langchain.messages import HumanMessage, SystemMessage, AIMessage
from app.services.model_service import ModelService
from app.services.milvus_service import MilvusService
from app.services.embedding_service import RemoteEmbeddingService

from .states import OverAllState, InputState, UserInputClassification, UserInputSplit, QueryMilvusState

logger = logging.getLogger(__name__)

# SQL 生成+执行最多尝试轮数：执行失败后带错误信息返回 sql_generator 重新生成，
# 累计失败达到该次数仍未成功，则走 sql_fallback 直接输出错误说明
SQL_MAX_ATTEMPTS = 3

model_service = ModelService()
milvus_service = MilvusService()
milvus_service.connect()
embedding_service = RemoteEmbeddingService()
model = model_service.load_llm_model()
RECALL_TOP_K = 7


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

    response = model.with_structured_output(UserInputSplit).invoke(messages)

    return {
        "user_input_split": response,
    }



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
        top_k=RECALL_TOP_K
    )

    # milvus_results = f"{user_input}的查询结果。"

    return {
        "milvus_results": [str(milvus_results)]
    }

def rag_agent(state: OverAllState) -> OverAllState:
    """
    rag_agent
    """
    user_input = state["user_input"]
    user_inputs = state["user_input_split"]["user_inputs"]
    user_input_real = state["user_input_split"]["user_input_real"]
    milvus_results = state["milvus_results"]

    system_content = load_prompt("raganalyzer")
    human_content = f"""
        用户输入{user_input}，拆分后的输入为：{user_inputs}，用户真实意图为：{user_input_real}，
        查询结果为：{milvus_results}
    """
    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=human_content)
    # 带入 checkpointer 按 thread_id 恢复的历史对话，保证多轮记忆
    history = state.get("messages") or []
    messages = [system_message] + history + [human_message]

    result = model.invoke(messages)
    return {
        "rag_result": result.content,
        # 历史只记"用户原问题+最终回答"，避免检索结果污染记忆
        "messages": [result]
    }

def _extract_sql(content: str) -> str:
    """从 LLM 输出中提取纯 SQL：优先取 ```sql 代码块，并规范化中文标点。"""
    match = re.search(r"```(?:\s*sql)?\s*(.*?)```", content, re.DOTALL | re.IGNORECASE)
    sql = match.group(1) if match else content
    # 中文弯引号/反引号会导致 SQL Server 语法错误，统一处理
    sql = (
        sql.replace("“", "'")
        .replace("”", "'")
        .replace("‘", "'")
        .replace("’", "'")
        .replace("`", "")
    )
    return sql.strip()


def sql_generator(state: OverAllState) -> OverAllState:
    """
    生成SQL查询语句

    若上一轮执行失败（state.sql_error 非空），把错误 SQL 与数据库报错
    一并带给模型，要求其修正后重新生成。
    """
    user_input = state["user_input"]
    system_content = load_prompt("sqlgenerator")
    # 带入历史对话，支持"再按月份汇总"之类的追问
    history = state.get("messages") or []
    messages = [SystemMessage(content=system_content)] + history

    sql_error = state.get("sql_error")
    if sql_error:
        retry_count = state.get("sql_retry_count", 0)
        human_content = (
            f"用户问题：{user_input}\n\n"
            f"你上一版生成的 SQL（执行失败）：\n{state.get('sql_str', '')}\n\n"
            f"数据库执行报错（第 {retry_count} 次失败）：\n{sql_error}\n\n"
            f"请根据报错信息修正 SQL，注意表名、字段名、字符引号与日期格式，"
            f"只输出修正后的 SQL 语句。"
        )
    else:
        human_content = user_input
    messages.append(HumanMessage(content=human_content))

    response = model.invoke(messages)

    return {
        "sql_str": _extract_sql(response.content),
        "sql_error": "",  # 新 SQL 尚未执行，清空旧错误
    }

def _fix_gbk_mojibake(value):
    """
    修复 FreeTDS 以 UTF-8 连接返回的 GBK 中文乱码：
    原始 GBK 字节被当作 latin-1/cp1252 解码，这里还原为正确中文。
    非字符串或正常 ASCII 数据原样返回。
    """
    if not isinstance(value, str) or not value:
        return value
    for enc in ("latin-1", "cp1252"):
        try:
            return value.encode(enc).decode("gbk")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return value


def sql_executor(state: OverAllState) -> OverAllState:
    """
    执行SQL查询语句

    执行失败时不抛异常，而是把错误信息写入 state.sql_error 并累加
    sql_retry_count，由条件边决定：返回 sql_generator 修正重试，
    或达到 SQL_MAX_ATTEMPTS 后走 sql_fallback 输出错误说明。
    """
    sql_str = state["sql_str"]
    sql_results = []
    # 连接数据库，执行SQL查询语句
    # charset 必须为 UTF-8：LLM 生成的 SQL 含中文条件（如商品名），
    # 该方向 FreeTDS 能正确转换；返回的 GBK 中文由 _fix_gbk_mojibake 还原。
    conn = None
    try:
        conn = pymssql.connect(
            server='208.208.0.252',
            user='sa',
            password='etc12+mdx',
            database='ytzy',
            port=1433,
            tds_version='7.0',
            charset='UTF-8')
        cursor = conn.cursor()
        cursor.execute(sql_str)
        for row in cursor.fetchall():
            sql_results.append(tuple(_fix_gbk_mojibake(col) for col in row))
        return {
            "sql_results": sql_results,
            "sql_error": "",
        }
    except Exception as e:
        retry_count = state.get("sql_retry_count", 0) + 1
        err_msg = f"{type(e).__name__}: {e}"
        logger.warning(f"SQL 执行失败（第 {retry_count} 次）: {err_msg}\nSQL: {sql_str}")
        return {
            "sql_results": [],
            "sql_error": err_msg,
            "sql_retry_count": retry_count,
        }
    finally:
        if conn is not None:
            conn.close()

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
    # 带入 checkpointer 恢复的历史对话，保证多轮记忆
    history = state.get("messages") or []
    messages = [system_message] + history + [human_message]
    response = model.invoke(messages)
    sql_analysis_result = response.content

    return {
        "sql_analysis_result": sql_analysis_result,
        # 历史只记"用户原问题+最终回答"
        "messages": [response]
    }

def other_agent(state: OverAllState) -> OverAllState:
    """
    其他查询
    """
    user_input = state["user_input"]
    human_message = HumanMessage(content=user_input)
    # 带入 checkpointer 恢复的历史对话，保证多轮记忆
    history = state.get("messages") or []
    result = model.invoke(history + [human_message])
    return {
        "other_results": result.content,
        "messages": [result]
    }


def sql_fallback(state: OverAllState) -> OverAllState:
    """
    SQL 连续 SQL_MAX_ATTEMPTS 次执行失败后的兜底节点：
    不再重试，直接基于错误原因向用户输出说明与排查建议。
    """
    user_input = state["user_input"]
    error = state.get("sql_error") or "未知错误"
    retry_count = state.get("sql_retry_count", 0)

    system_content = (
        "你是数据库查询助手。SQL 语句已连续多次执行失败，无法获取业务数据。"
        "请用中文向用户说明失败原因，并给出可操作的排查建议（例如核对药品名称、"
        "时间范围、查询条件等），不要编造任何数据。"
    )
    user_content = (
        f"用户问题：{user_input}\n"
        f"SQL 已连续 {retry_count} 次生成并执行失败。最后一次数据库错误信息：\n{error}"
    )
    history = state.get("messages") or []
    messages = (
        [SystemMessage(content=system_content)]
        + history
        + [HumanMessage(content=user_content)]
    )
    response = model.invoke(messages)
    logger.error(f"SQL 重试 {retry_count} 次仍失败，走兜底说明: {error}")
    return {
        "sql_analysis_result": response.content,
        "messages": [response],
    }


