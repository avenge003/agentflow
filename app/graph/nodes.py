from pathlib import Path
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
    system_content = f"""
        你是一个专业的语义分类助手，只能对用户输入进行分类，不能进行其他操作，分类结果只能是rag、sql或other，
        如果是用户输入的文本是关于药厂制度文件等相关的，分类结果为rag
        如果是用户输入的文本是关于销售采购库存等经营数据相关的，分类结果为sql
        如果是用户输入的文本是关于其他等相关的，分类结果为other
    """
    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=user_input)
    messages = [system_message, human_message]
    
    response = model.with_structured_output(UserInputClassification).invoke(messages)

    return {
        "user_input": user_input,
        "classification": response["classification"]
    }

def split_user_input(state: OverAllState) -> OverAllState:
    """
    对用户输入进行拆分
    """
    user_input = state["user_input"]
    system_content = f"""
        你是一个专业的用户输入拆分助手，
        对用户输入的文本进行分析，并拆分成多个可以用来检索知识库的子文本（10个以内），
        拆分内容必须是与药厂制度文件，药品质量，药品相关法律法规等相关的
        识别出用户输入的真实意图。
    """
    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=user_input)
    messages = [system_message, human_message]
    
    user_input_split = model.with_structured_output(UserInputSplit).invoke(messages)

    return {
        "user_input_split": user_input_split
    }

def rag_router(state: OverAllState) -> Sequence[Send]:
    """
    rag_agent
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
    system_content = f"""
        你是一个专业的Text2SQL助手，针对用户输入的文本，生成对应的SQL查询语句。
        生成的SQL查询语句必须是正确的MSSQLServer的SQL语法，不能包含任何错误或无效的SQL语句。
        生成的SQL查询语句是关于药厂的物料采购、物料成品库存以及成品销售等数据查询语句。
        查询结果尽量详细。
        数据库表结构如下： 
        商品流水表：splsk,spid:商品内码,rq:日期,dwbh:单位内码,pihao:商品批号,
            djbh:单据编号(JHA开头：采购入库单，JHC开头：采购退出单，JHB开头：采购退补价单，XSA开头：销售出库单，XSC开头：销售退出单，XSB开头：销售退补价单),
            rkshl:入库数量,rkdj:入库单价,rkje:入库金额,chkshl:出库数量,chkje:出库金额,xshe:销售额
        商品货位批号库存表：sphwph,spid:商品内码,pihao:商品批号,shl:库存数量
        商品资料表：spkfk,spid:商品内码,spbh:商品编号,spmch:商品名称,shpgg:商品规格,dw:单位,shpchd:商品产地,shengccj:生产厂家,leibie:商品类型
        采购销售单位表：mchk,dwbh:单位内码,danwbh:单位编号,dwmch:单位名称,ywy:业务员,isjh:是否是采购单位(是，否),isxs:是否是销售单位(是，否),dzhdh:联系地址
    """
    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=user_input)
    messages = [system_message, human_message]
    
    response = model.invoke(messages)

    return {
        "sql_str": response.content.replace("```sql", "").replace("```", "")
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

    system_content = f"""
        你是一个专业的企业经营数据分析助手。
        针对查询到的业务数据，从药厂角度进行分析。
        从多个维度进行分析，包括但不限于：
        1. 商品销售趋势
        2. 采购销售单位的采购销售趋势
        3. 商品库存趋势
        4. 商品销售金额趋势
        5. 商品销售数量趋势
        分析结果必须是中文。
        分析结果分项分类输出。
    """
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
        "sql_analysis_result": sql_analysis_result
    }


def other_agent(state: OverAllState) -> OverAllState:
    """
    其他查询
    """
    user_input = state["user_input"]
    result = model.invoke([HumanMessage(content=user_input)])
    return {
        "other_results": result.content
    }


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