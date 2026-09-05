from langchain.tools import tool
from langchain.chat_models import init_chat_model

model = init_chat_model(
    "qwen3.7-plus-2026-05-26",
    model_provider="openai",
    temperature=0.5,
    max_tokens=1024,
    timeout=60,
    max_retries=3,
    base_url="https://llm-i61zzg24x42f4pyj.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    api_key="sk-3477824d550d41deb3b892a58b269973",
)

# Define tools
@tool
def multiply(a:int, b:int) -> int:
    """Multiply two numbers."""
    return a * b

@tool
def add(a:int, b:int) -> int:
    """Add two numbers."""
    return a + b

@tool
def devide(a:int, b:int) -> int:
    """Divide two numbers."""
    return a / b


tools = [add, multiply, devide]
tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)

# Define state
from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage],operator.add]
    llm_calls:int

# Define model node
from langchain.messages import SystemMessage
def llm_call(state:dict):
    """
    LLM decides whether to call a tool or not.
    """
    return {
        "messages":[
            model_with_tools.invoke(
                [
                    SystemMessage(
                        content = "You are a helpful assistent tasked with performing arithmetic on a set of inputs."
                    )
                ]
                + state["messages"]
            )
        ],
        "llm_calls":state.get("llm_calls", 0) + 1
    }

# Define tool node
from langchain.messages import ToolMessage

def tool_node(state:dict):
    """
    Performs the tool call.
    """
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
        
    return {
        "messages":result
    }

# Define end logic
from typing import Literal
from langgraph.graph import StateGraph, START, END

def should_continue(state:MessagesState) -> Literal["tool_node", END]:
    """
    Decide if we should continue the loop or stop based upon whether the LLM made a tool call.
    """
    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, then perform an action.
    if last_message.tool_calls:
        return "tool_node"

    # Otherwise, we stop(reply to the user).
    return END


# Build and complie the agent
# Build workflow
agent_builder = StateGraph(MessagesState)

# Add nodes
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    ["tool_node", END]
)
agent_builder.add_edge("tool_node", "llm_call")

# Compile the agent
agent = agent_builder.compile()

# Show the agent
from IPython.display import Image, display
display(Image(agent.get_graph(xray=True).draw_mermaid_png()))

# Invoke the agent
from langchain.messages import HumanMessage
messages = [HumanMessage(content="Divide 5 and 2.")]
messages = agent.invoke({"messages":messages})
for m in messages["messages"]:
    m.pretty_print()
