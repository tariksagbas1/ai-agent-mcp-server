import asyncio
import os
import requests
import json
from dotenv import load_dotenv
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from fastapi import FastAPI, Request
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import StateGraph, START, END
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from fastmcp import Client
from contextlib import asynccontextmanager

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MCP_SERVER_URL = "http://127.0.0.1:8000/mcp/"

memory = MemorySaver()
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0, model="gpt-4o")



system_prompt = """
You are an AI asisstant for the company Icron.
You're name is Icron Agent.
Greet the user with your name and ask them how you can help them if it is the first time you have been prompted.
You have to use your tools to answer the user's questions.
"""

def mcp_tool_call(tool_name, input_dict):
    """
    Generic function to call an MCP tool by name with arguments.
    Handles both JSON and SSE (Server-Sent Events) responses.
    """
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params" : {
            "name": tool_name,
            "arguments": input_dict,
        },
    }
    resp = requests.post(
        MCP_SERVER_URL,
        json=payload,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
    )
    try:
        resp.raise_for_status()
        # Check for SSE (Server-Sent Events) response
        if resp.text.startswith("event: message"):
            # Find the line starting with 'data: '
            for line in resp.text.splitlines():
                if line.startswith("data: "):
                    data_json = line[len("data: "):].strip()
                    try:
                        data = json.loads(data_json)
                        # If it's a JSON-RPC response, extract 'result' if present
                        if isinstance(data, dict) and "result" in data:
                            return data["result"]
                        return data
                    except Exception as e:
                        return f"Error parsing SSE data: {e}\nRaw data: {data_json}"
            return "Error: No 'data:' line found in SSE response."
        else:
            # Fallback: try to parse as JSON
            return resp.json().get("result", resp.text)
    except Exception as e:
        return f"Error calling MCP tool '{tool_name}': {e}\nResponse: {resp.text}"


# --- Tool Functions ---

def get_employees(input_dict):
    print(input_dict, type(input_dict))
    if isinstance(input_dict, str):
        try:
            input_dict = json.loads(input_dict)
        except Exception:
            input_dict = {"name": input_dict}
    return mcp_tool_call("get_employees", input_dict)

def send_mail(input_dict):
    print(input_dict, type(input_dict))
    if isinstance(input_dict, str):
        try:
            input_dict = json.loads(input_dict)
        except Exception:
            input_dict = {"to": input_dict}
    return mcp_tool_call("send_mail", input_dict)

def get_date_time(input_dict):
    print(input_dict, type(input_dict))
    if isinstance(input_dict, str):
        try:
            input_dict = json.loads(input_dict)
        except Exception:
            input_dict = {"timezone": input_dict}
    return mcp_tool_call("get_date_time", input_dict)

# --- Tool List ---
tools = [
    Tool(
        name="get_date_time",
        func=get_date_time,
        description=(
             """
        Gets the current date and time in a given timezone. \n
    Args:
        timezone: Timezone name (eg. Europe/Istanbul, America/New_York, etc.)
        Defaults to Europe/Istanbul
    Returns:
        The current date and time in the given timezone as a JSON object.
    """
        )
    ),
    Tool(
        name="get_employees",
        func=get_employees,
        description=(
            """
        Get the information of the employees in the company ICRON. Optionally filters by department, gender, office, rank, and day of the week. \n
    Args:
        name: The name of the employee
        department: The department of the employee
        gender: The gender of the employee
        office: The office of the employee
        rank: The rank of the employee
        office_days: The days of the week the employee works in the office (Monday, Tuesday, Wednesday, Thursday, Friday)
        requested_info: The information to be returned about the employees (name, department, gender, office, rank, monday, tuesday, wednesday, thursday, friday)
        only_count: Whether to return only the count of the employees or the employees with their attributes (True/False)
    Example Input:
        {"name": "John Doe", "department": "Product", "gender": "male", "office": "Istanbul", "rank": "Senior", "office_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "requested_info": ["name", "department", "gender", "office", "rank", "monday", "tuesday", "wednesday", "thursday", "friday"], "only_count": False}
    Returns:
        The employees with their attributes as a JSON object.
    """
        )
    ),
    Tool(
        name="send_mail",
        func=send_mail,
        description=(
            """
        Sends an email using the Gmail API.\n
    Args:
        to: The email address of the recipient
        subject: The subject of the email
        body: The body of the email
        cc: The email address of the carbon copy recipient
        bcc: The email address of the blind carbon copy recipient
    Returns:
        The sent email info as a JSON object.
    """
        )
    )
]


# --- Define State Schema ---
class State(TypedDict):
    messages: Annotated[list, add_messages]
    allowed_tools: list
    cache_allowed_tools: list

# --- Build the StateGraph ---
graph_builder = StateGraph(State)

def pick_tools_node(state: State):
    print("Getting tools...")
    user_prompt = state["messages"][-1].content
    res = mcp_tool_call("pick_tools", {"user_prompt": user_prompt})
    res = json.loads(res.get("content")[0].get("text")).get("result")
    selected_tools = json.loads(res)
    print(f"Selected Tools: {selected_tools}")
    state["allowed_tools"] = selected_tools
    return state

def agent_node(state: State):
    print("Calling Agent...")
    selected_tools = state.get("allowed_tools", [])
    filtered_tools = [tool for tool in tools if tool.name in selected_tools]
    agent = create_react_agent(llm, tools=tools, prompt=system_prompt) # Change this later to filtered_tools
    try:
        result = agent.invoke({"messages": state["messages"]})
    except Exception as e:
        print(e)
        state["messages"].append({"role": "assistant", "content": "I'm sorry, I'm having trouble processing your request. Please try again."})
        return state
    
    if "messages" in result:
        state["messages"].extend(result["messages"])
    else:
        state["messages"].append(result)
    
    
    agent_response = result["messages"][-1].content
    print(agent_response)
    try:
        return state
    except Exception as e:
        print(e)
        state["messages"].append(AIMessage(content="I'm sorry, I'm having trouble processing your request. Please try again."))
        return state

# Add nodes and edges as per docs
graph_builder.add_node("pick_tools", pick_tools_node)
graph_builder.add_node("agent", agent_node)

graph_builder.add_edge(START, "pick_tools")
graph_builder.add_edge("pick_tools", "agent")
graph_builder.add_edge("agent", END)

graph = graph_builder.compile(checkpointer=memory)

MCPtools = []
@asynccontextmanager
async def lifespan(app : FastAPI):
    global MCPtools
    async with Client(MCP_SERVER_URL) as client:
        MCPtools = await client.list_tools()
    for tool in MCPtools:
        print(f"Tool: {tool.name}")
        print(f"Description: {tool.description}")
        if hasattr(tool, "inputSchema"):
            print(f"Parameters: {tool.inputSchema}")
        #tools.append(Tool(name=tool.name, func=make_tool_func(tool.name), description=tool.description))
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify ["http://127.0.0.1:5500"] for more security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/agent")
async def run_agent(req : Request):
    data = await req.json()
    session_id = data.get("session_id")
    question = data.get("question")

    print("User input:", question)
    print("Session ID:", session_id)

    config = {"configurable": {"thread_id": session_id}}

    state = State()
    state["messages"] = [HumanMessage(content=question)]
    final_state = graph.invoke(state, config)
    agent_response = final_state["messages"][-1].content
    return {"response": agent_response}
    




if __name__ == "__main__":
    uvicorn.run("lg_agent:app", host="0.0.0.0", port=8080, reload=True)

