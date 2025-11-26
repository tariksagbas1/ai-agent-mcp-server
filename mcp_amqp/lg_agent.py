import asyncio
import os
import requests
import json
from dotenv import load_dotenv
from langchain.tools import Tool, StructuredTool
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
from pydantic import create_model
from fastapi import Response

load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "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"
os.environ["LANGSMITH_PROJECT"] = "pr-worthwhile-harmony-90"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MCP_SERVER_URL = "http://127.0.0.1:8000/mcp/"
CONFIG_FILE_PATH = "config/config.idep"

memory = MemorySaver()
model_name = "gpt-4o-mini"
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0, model=model_name)
tools = []


system_prompt = """
You are an AI asisstant for the company Icron.
Your users are from the company Icron.
You're name is Icron Agent.
You have to use your tools to answer the user's questions.
Instructions on how to use tools:
- Example usage: tool_func(input_dict : dict),
- input_dict is a dictionary of arguments for the tool. Format is {"arg1": "value1", "arg2": "value2", ...}
"""
# ---- Helper Functions ----
def get_allowed_tools(config_file_path : str):
    try:
        with open(config_file_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading config file: {e}")
        return []
    
    for service in data["Services"]:
        if "LLMServiceOptions" in service:
            return service["LLMServiceOptions"].get("MCPTools")
            
def schema_to_pydantic(name, schema):
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    fields = {}
    for arg, props in schema.get("properties", {}).items():
        typ = type_map.get(props.get("type", "string"), str)
        default = props.get("default", None)
        fields[arg] = (typ, default)
    return create_model(f"{name}_Args", **fields)


# --- Tool Function Wrappers ---

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
    

def make_tool_func(tool_name, input_schema):
    # Get the argument names from the schema
    arg_names = list(input_schema.get("properties", {}).keys()) if input_schema else []

    def tool_func(**kwargs):
        print(f"[TOOL CALL]   {tool_name} with {kwargs}")
        return mcp_tool_call(tool_name, kwargs)
        # If input is a string, wrap it in a dict with the correct argument name
        print(input_dict, type(input_dict))
        if isinstance(input_dict, str):
            try:
                input_dict = json.loads(input_dict)
            except Exception:
                if len(arg_names) == 1:
                    input_dict = {arg_names[0]: input_dict}
                else:
                    print(f"Error parsing input: {input_dict}")
        return mcp_tool_call(tool_name, input_dict)
    return tool_func


# --- Define State Schema ---
class State(TypedDict):
    messages: Annotated[list, add_messages]
    allowed_tools: list
    cache_allowed_tools: list

# --- Build the StateGraph ---
graph_builder = StateGraph(State)

def pick_tools_node(state: State):
    print("Getting tools...")
    #user_prompt = state["messages"][-1].content
    #res = mcp_tool_call("pick_tools", {"user_prompt": user_prompt})
    #res = json.loads(res.get("content")[0].get("text")).get("result")
    #selected_tools = json.loads(res)
    #print(f"Selected Tools: {selected_tools}")
    #state["allowed_tools"] = tools
    return state

def agent_node(state: State):
    print("Calling Agent...")
    selected_tools = state.get("allowed_tools", [])
    filtered_tools = [tool for tool in tools if tool.name in selected_tools]
    llm_with_tools = llm.bind_tools(tools)
    agent = create_react_agent(llm_with_tools, tools=tools, prompt=system_prompt)
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
    print(f"[AGENT]       {agent_response}")
    try:
        return state
    except Exception as e:
        print(e)
        state["messages"].append(AIMessage(content="I'm sorry, I'm having trouble processing your request. Please try again."))
        return state

# Add nodes and edges as per docs
graph_builder.add_node("PICK_TOOLS", pick_tools_node)
graph_builder.add_node("TRIGGER_AGENT", agent_node)

graph_builder.add_edge(START, "PICK_TOOLS")
graph_builder.add_edge("PICK_TOOLS", "TRIGGER_AGENT")
graph_builder.add_edge("TRIGGER_AGENT", END)

graph = graph_builder.compile(checkpointer=memory)

all_tools = []
@asynccontextmanager
async def lifespan(app : FastAPI):
    print("Getting tools from MCP Server...")
    print("======= Available Tools =======")
    global all_tools
    # Fetch all tools from MCP Server
    async with Client(MCP_SERVER_URL) as client:
        all_tools = await client.list_tools()
    
    for tool in all_tools:
        print(f"Tool: {tool.name}")
        if hasattr(tool, "inputSchema"):
            pyd_model = schema_to_pydantic(tool.name, tool.inputSchema)
            tools.append(
                StructuredTool(
                    name=tool.name,
                    func=make_tool_func(tool.name, tool.inputSchema),
                    description=tool.description,
                    args_schema=pyd_model
                )
            )
        else:
            tools.append(Tool(name=tool.name, func=make_tool_func(tool.name, None), description=tool.description))
    for tool in tools:
        #print(tool.get_input_jsonschema())
        print()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify ["http://127.0.0.1:5500"] for more security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/mcp_proxy")
async def mcp_proxy(req : Request):
    request_data = await req.json()
    try:
        response = requests.post(
            MCP_SERVER_URL,
            json=request_data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )
        return Response(content=response.text, media_type="text/event-stream")
    except Exception as e:
        print(e)
        return {"error": str(e)}



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
    load_dotenv()
    uvicorn.run("lg_agent:app", host="0.0.0.0", port=8080, reload=True)
