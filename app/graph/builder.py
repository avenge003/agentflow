from langgraph.graph import StateGraph, START, END
from .state import OverAllState, InputState
from .nodes import classify_user_input,sql_generator,other_agent,split_user_input,query_milvus,sql_executor,sql_analyzer
from .routers import rag_router,classification_router

def build_graph():
    builder = StateGraph(state_schema=OverAllState, input_schema=InputState)
    builder.add_node("classify_user_input", classify_user_input)    # 对用户输入进行分类
    builder.add_node("sql_generator", sql_generator)                    # sql_generator
    builder.add_node("other_agent", other_agent)                # other_agent
    builder.add_node("split_user_input", split_user_input)    # 对用户输入进行拆分
    builder.add_node("query_milvus", query_milvus)            # 查询Milvus
    builder.add_node("sql_executor", sql_executor)            # 执行SQL查询语句
    builder.add_node("sql_analyzer", sql_analyzer)            # 分析SQL查询结果

    builder.add_edge(START, "classify_user_input")
    builder.add_conditional_edges("classify_user_input", classification_router)
    builder.add_conditional_edges("split_user_input", rag_router, path_map=["query_milvus"])
    builder.add_edge("query_milvus", END)
    builder.add_edge("sql_generator", "sql_executor")
    builder.add_edge("sql_executor", "sql_analyzer")
    builder.add_edge("sql_analyzer", END)
    builder.add_edge("other_agent", END)

    graph = builder.compile()

    return graph