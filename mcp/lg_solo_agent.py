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

from typing import Annotated


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MCP_SERVER_URL = "http://127.0.0.1:8000/mcp/"

# --- Helper Functions ---
def print_agent_history(agent_response, tools_called = []):
    print("*" * 80)
    print("*" * 80)
    print("*" * 80)
    print("Agent Response:", agent_response)
    print()
    for i, tool in enumerate(tools_called):
        print(f"{i+1}) {list(tool.keys())[0]} \n Arguments: {list(tool.values())[0]}")
        print()
    print()
    print()

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
def get_employees_tool(input_dict):
    if isinstance(input_dict, str):
        try:
            input_dict = json.loads(input_dict)
        except Exception:
            input_dict = {"name": input_dict}
    return mcp_tool_call("get_employees", input_dict)

def send_mail_tool(input_dict):
    if isinstance(input_dict, str):
        try:
            input_dict = json.loads(input_dict)
        except Exception:
            input_dict = {"to": input_dict}
    return mcp_tool_call("send_mail", input_dict)

def get_date_time_tool(input_dict):
    if isinstance(input_dict, str):
        try:
            input_dict = json.loads(input_dict)
        except Exception:
            input_dict = {"timezone": input_dict}
    return mcp_tool_call("get_date_time", input_dict)

# --- Tool List ---
tools = [
    Tool(
        name="get_employees",
        func=get_employees_tool,
        description=(
            """
        Get the employees in the company. Optionally filters by department, gender, office, rank, and day of the week. \n
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
        func=send_mail_tool,
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
    ),
    Tool(
        name="get_date_time",
        func=get_date_time_tool,
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
]


# --- LLM and Agent Setup ---
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0, model="gpt-4o")


system_prompt = """
You are an AI asisstant for the company Icron.
You're name is Icron Agent.
Greet the user with your name and ask them how you can help them.
You're task is to help the user with their questions.
You can use the tools provided to you to answer the user's questions.
"""
# Create the LangGraph ReAct agent
agent = create_react_agent(llm, tools=tools, prompt=system_prompt)

app = FastAPI()
history = []


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

    

    global history
    history.append({"role": "user", "content": question})

    if "question" in data:
        user_input = {"messages": [{"role": "user", "content": data["question"]}]}
    else:
        return {"error": "Missing 'question' or 'messages' in request."}


    steps = agent.stream({"messages": history}, stream_mode="updates")
    tools_called = []
    for step in steps:
        
        # Log Agent Steps
        
        # 1. Print agent messages (thoughts, answers, etc.)
        messages = step.get('agent', {}).get('messages', [])
        for msg in messages:
            if hasattr(msg, "content") and msg.content:
                print("-" * 60)
                print("Agent message:", msg.content)

        # 2. Print tool calls (when the agent decides to use a tool)
        for msg in messages:
            # Check for tool_calls in additional_kwargs (for OpenAI function calling)
            tool_calls = getattr(msg, "additional_kwargs", {}).get("tool_calls", [])
            for call in tool_calls:
                print("-" * 60)
                print(f"Tool call: {call['function']['name']} with arguments {call['function']['arguments']}")
                tools_called.append({call['function']["name"] : call["function"]["arguments"]})
        
        # 3. Print tool results (ToolMessage content)
        tool_msgs = step.get('tools', {}).get('messages', [])
        for tool_msg in tool_msgs:
            if hasattr(tool_msg, "content"):
                print("-" * 60)
                print("Tool result:", tool_msg.content)
        
        # 4. Get Final Answer of Agent
        if "agent" in step:
            message = step.get("agent").get("messages")[-1]
            if hasattr(message, "content") and message.content:
                agent_response = getattr(message, "content")
                history.append({"role": "assistant", "content": agent_response})
                print_agent_history(agent_response, tools_called)
                return {"response": agent_response}



if __name__ == "__main__":
    print()
    uvicorn.run("lg_agent:app", host="0.0.0.0", port=8080, reload=True)
