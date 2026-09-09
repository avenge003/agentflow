from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from .states import OverAllState, InputState
from .nodes import classify_user_input,sql_generator,other_agent,split_user_input,query_milvus,sql_executor,sql_analyzer,rag_agent,sql_fallback
from .routers import rag_router,classification_router,sql_exec_router

checkpointer = InMemorySaver()

def build_graph():
    builder = StateGraph(state_schema=OverAllState, input_schema=InputState)
    builder.add_node("classify_user_input", classify_user_input)    # 对用户输入进行分类
    builder.add_node("sql_generator", sql_generator)                    # sql_generator
    builder.add_node("other_agent", other_agent)                # other_agent
    builder.add_node("split_user_input", split_user_input)    # 对用户输入进行拆分
    builder.add_node("query_milvus", query_milvus)            # 查询Milvus
    builder.add_node("sql_executor", sql_executor)            # 执行SQL查询语句
    builder.add_node("sql_analyzer", sql_analyzer)            # 分析SQL查询结果
    builder.add_node("sql_fallback", sql_fallback)            # SQL 多次失败后的错误说明
    builder.add_node("rag_agent", rag_agent)                    # rag_agent

    builder.add_edge(START, "classify_user_input")
    builder.add_conditional_edges("classify_user_input", classification_router)
    builder.add_conditional_edges("split_user_input", rag_router, path_map=["query_milvus"])
    builder.add_edge("query_milvus", "rag_agent")
    builder.add_edge("rag_agent", END)

    builder.add_edge("sql_generator", "sql_executor")
    # 执行成功→分析；失败且未达上限→带错误回 sql_generator 重试；达上限→错误说明
    builder.add_conditional_edges(
        "sql_executor",
        sql_exec_router,
        ["sql_analyzer", "sql_generator", "sql_fallback"],
    )
    builder.add_edge("sql_analyzer", END)
    builder.add_edge("sql_fallback", END)
    builder.add_edge("other_agent", END)

    graph = builder.compile(checkpointer=checkpointer)

    return graph