from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import os
from langchain.tools import tool
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

load_dotenv()

# 用@tool装饰器定义一个工具
@tool
def get_weather(city:str)->str:
    """
    获取城市的天气信息
    Args:
        city (str): 城市名称
    Returns:
        str: 城市的天气信息
    """
    weather_data = {
        "杭州":"晴，25℃，风速3级，湿度 60%",
        "北京":"多云，20℃，风速5级，湿度 40%",
        "上海":"晴，24℃，风速2级，湿度 50%",
        "广州":"多云，22℃，风速4级，湿度 30%",
        "深圳":"晴，26℃，风速3级，湿度 70%",
    }
    return weather_data.get(city, "未找到该城市的天气信息")

@tool
def calculate(expression:str) -> str:
    """
    计算表达式,支持加减乘除四则运算,结果保留两位小数。
    Args:
        expression (str): 表达式,例如 "1+2" 或 "3*4+6"
    Returns:
        str: 计算结果
    """
    try:
        # 安全地计算数学表达式
        result = eval(expression, {"__builtins__": {}},{})
        return f"计算结果：{expression}={result}"
    except Exception as e:
        return f"计算表达式 {expression} 时出错：{str(e)}"

# 创建Agent
# 初始化模型
model = init_chat_model(
    "qwen3.7-plus-2026-05-26",
    model_provider="openai",
    temperature=0.5,
    max_tokens=1024,
    timeout=60,
    max_retries=3,
    base_url=os.getenv("DASHSCOPE_API_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY")
)

# 创建Agent，传入模型和工具列表
# agent = create_agent(
#     model = model,
#     tools = [get_weather, calculate],
#     system_prompt = "你是一个乐于助人的助手，会使用工具来回答问题"
# )

# 运行Agent
from langchain.messages import HumanMessage

def singletool(question:str):
    inputs = {
        "messages": [HumanMessage(content=question)]
    }

    result = agent.invoke(inputs)

    print("=== 完整的消息历史 ===")
    for message in result["messages"]:
        print(f"[{message.type}] {message.content[:100]}")  # 截取前100个字符

    print("\n=== 最终回答 ===")
    print(result["messages"][-1].content)

def multtool(question:str):
    inputs = {
        "messages":[HumanMessage(
            content=question
        )]
    }

    result = agent.invoke(inputs)

    print("=== 完整的消息历史 ===")
    for message in result["messages"]:
        if message.type == "tool":
            print(f"[tool {message.name}] {message.content}")
        else:
            print(f"[{message.type}] {message.content[:120]}")  # 截取前120个字符

    print("\n=== 最终回答 ===")
    print(result["messages"][-1].content)

import asyncio

async def main():
    inputs = {
        "messages":[HumanMessage(
            content="深圳与北京今天天气有什么不同？"
        )]
    }

    result = await agent.ainvoke(inputs)
    print(result["messages"][-1].content)

# asyncio.run(main())

# 绑定工具
def bindtools():
    # 用字典描述工具（OpenAI function calling 格式）
    tools = [
        {
            "type": "function",
            "function":{
                "name":"get_weather",
                "description": "查询指定城市的天气",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city":{
                            "type": "string",
                            "description": "城市名称，如 杭州、北京"
                        }
                    }
                },
                "required": ["city"]
            }
        }
    ]

    # 将工具绑定到模型
    model_with_tools = model.bind_tools(tools)


    # 问一个问题
    response = model_with_tools.invoke("深圳与北京今天天气有什么不同？")
    
    if response.tool_calls:
        print("模型请求调用以下工具：")
        for tc in response.tool_calls:
            print(f" 工具名： {tc['name']}")
            print(f" 参数： {tc['args']}")
            print(f" 调用ID： {tc['id']}")
    else:
        print(f"模型直接回复：{response.content}")


# 用Pydantic模型描述工具
from pydantic import BaseModel, Field

# 用Pydantic定义工具的参数结构
class WeatherInput(BaseModel):
    """
    查询城市的天气信息
    """
    city: str = Field(description="城市名称，如 杭州、北京")
    unit: str = Field(
        default= "celsius",
        description="温度单位，celsius（摄氏度）或fahrenheit（华氏度）"
    )

class CalculateInput(BaseModel):
    """
    计算表达式
    """
    expression: str = Field(description="数学表达式,例如 '1+2' 或 '3*4+6'")


def pydantic_tool():
    # 传入Pydantic模型，LangChain自动转换为工具描述
    model_with_tools = model.bind_tools([WeatherInput, CalculateInput])
    response = model_with_tools.invoke("北京今天天气怎么样？顺便计算一下319*274")
    
    print(f"模型请求了 {len(response.tool_calls)} 个工具调用：")
    for tc in response.tool_calls:
        print(f"  {tc['name']}({tc['args']})")


# pydantic_tool()


# with_structured_output() 让模型返回结构化输出

# 定义期望的输出结构
class PersionInfo(BaseModel):
    """
    从文本中提取的任务信息
    """
    name:str = Field(description="人物姓名")
    age:int = Field(description="年龄")
    occupation:str = Field(description="职业")
    skills:list[str] = Field(description="技能列表")


def structured_output_tool():
    structured_model = model.with_structured_output(PersionInfo)

    text = "张三是一个25岁的前端开发，他的职业是前端开发，他的技能包括HTML、CSS、JavaScript、React等。"
    result = structured_model.invoke(text)
    print(f"姓名：{result.name}")
    print(f"年龄：{result.age}")
    print(f"职业：{result.occupation}")
    print(f"技能：{', '.join(result.skills)}")
    print(f"类型：{type(result)}")


# structured_output_tool()

class Ingredient(BaseModel):
    """
    食材信息
    """
    name:str = Field(description="食材名称")
    amount:str = Field(description="用量，如 100g、200ml、2个")

class CookingStep(BaseModel):
    """
    烹饪步骤
    """
    step_number: int = Field(description="步骤编号")
    description:str = Field(description="步骤描述")
    duration_minutes: int = Field(description="步骤持续时间（分钟）")

class Recipe(BaseModel):
    """
    菜谱
    """
    dish_name:str = Field(description="菜名")
    difficulty:str = Field(description="难度等级，如 简单、中等、困难")
    ingredients:list[Ingredient] = Field(description="食材列表")
    steps:list[CookingStep] = Field(description="烹饪步骤")


def recipe_tool():
    structured_model = model.with_structured_output(Recipe)

    # 输入一个菜谱描述
    recipe_text = """
    今天来教大家做一道经典的番茄炒蛋，这道菜非常简单。
    需要准备：番茄 2 个、鸡蛋 3 个、葱花少许、盐适量、糖少许。
    步骤：
    1. 先把番茄切块，鸡蛋打散，大概需要 5 分钟
    2. 热锅放油，先把鸡蛋炒熟盛出，大概 3 分钟
    3. 锅中再放油，炒番茄至出汁，加盐和糖，大概 5 分钟
    4. 倒入炒好的鸡蛋，翻炒均匀，撒上葱花，大概 2 分钟
    """

    result = structured_model.invoke(recipe_text)
    
    print(f"菜名: {result.dish_name}")
    print(f"难度: {result.difficulty}")
    print(f"食材 ({len(result.ingredients)} 种):")
    for ing in result.ingredients:
        print(f"  - {ing.name}: {ing.amount}")
    print(f"步骤 ({len(result.steps)} 步):")
    for step in result.steps:
        print(f"  {step.step_number}. {step.description} ({step.duration_minutes}分钟)")

# recipe_tool()

# return_direct() 直接返回最终结果
# 普通工具：结果返回给模型，模型再做总结
@tool
def search_normal(keyword: str) -> str:
    """
    普通搜索工具，返回搜索结果
    """
    return f"搜索结果：Python3 基础教程、Python 数据分析、Python 爬虫入门"

# return_direct 工具
@tool(return_direct=True)
def search_direct(keyword: str) -> str:
    """
    直接返回搜索结果，不需要额外分析时使用此工具
    """
    return f"搜索结果：Python3 基础教程、Python 数据分析、Python 爬虫入门"

def ask_direct(question: str):
    agent_normal = create_agent(
        model,
        tools=[search_normal],
        system_prompt="你是菜鸟教程的学习顾问。"
    )

    agent_direct = create_agent(
        model,
        tools=[search_direct],
        system_prompt="你是菜鸟教程的学习顾问。"
    )

    # 普通模式
    result = agent_normal.invoke({
        "messages":[HumanMessage(content=question)]
    })
    print("=== 普通模式(模型会加工) ===")
    print(result["messages"][-1].content[:150])

    # 直接模式
    result = agent_direct.invoke({
        "messages":[HumanMessage(content=question)]
    })
    print("=== 直接模式(模型不会加工) ===")
    print(result["messages"][-1].content[:150])


ask_direct("搜索 Python 课程")



## singletool("杭州今天天气怎么样？")
# singletool("杭州和北京今天温差多少度？")
# singletool("菜鸟教程 RUNOOB 是一个非常棒的学习平台，如果我有 3 个朋友都推荐了，再加上 2 个，一共多少人推荐？")


# multtool()