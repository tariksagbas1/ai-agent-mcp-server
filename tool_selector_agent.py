import json
import os
from openai import OpenAI
from dotenv import load_dotenv
from fastmcp import Client
import asyncio
from fastapi import FastAPI, Request
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify your frontend's URL for more security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MCP_SERVER_URL = "http://127.0.0.1:8000/mcp/"


@app.post("/agent")
async def get_tools(req : Request):

    async with Client(MCP_SERVER_URL) as client:
        all_tools = await client.list_tools()
    
    
    
    openai_tools = []
    for tool in list(all_tools):
        print()
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        # Populate dynamically
                    },
                "additionalProperties": False
                }
            }
        }
        for key, value in tool.inputSchema.get("properties").items():
            if value.get("type") == "array":
                openai_tool["function"]["parameters"]["properties"][key] = {
                    "type": value.get("type"),
                    "items": value.get("items")
                }
            else:
                openai_tool["function"]["parameters"]["properties"][key] = {
                    "type": value.get("type"),
                }
        openai_tools.append(openai_tool)
    
    data = await req.json()
    user_prompt = data.get("question")

    #system_prompt = "You are a tool selector. You should pick multiple tools. Pick every single tool and their arguments to satisfy the user's request. Execute these tools with the necessary arguments. Respond with Error! if you come accross a problem. If you deem no need for any tools, do not execute any tools."
    #user_message = f"Given the user query: \"{user_prompt}\"\nSelect every tool that can be used to satisfy the user's request."
    system_prompt = """You choose one or multiple tools according to Turkish or English user queries about some employee shift management data. The tools chosen by you will be used by a python programmer agent.
                     While choosing a tool, you must consider what are the data fields written in the tool description, since multiple tables would be needeed as merged data related to a given user query."""

    client = OpenAI(api_key=OPENAI_API_KEY)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            tools=openai_tools,
            parallel_tool_calls=True,
            temperature=0
        )
        
    except Exception as e:
        print("ERROR IS :", e)
        return {"result": json.dumps({"error": f"Error picking tools: {e}"})}
    
    print("Response Message:", response.choices[0].message)

    # Handle both regular tool calls and parallel tool calls
    selected_tools = []
    
    if response.choices[0].message.tool_calls:
        # Regular tool calls
        for tool_call in response.choices[0].message.tool_calls:
            selected_tools.append({
                "name": tool_call.function.name,
                "arguments": json.loads(tool_call.function.arguments)
            })
    elif hasattr(response.choices[0].message, 'parallel_tool_calls') and response.choices[0].message.parallel_tool_calls:
        # Parallel tool calls
        for parallel_call in response.choices[0].message.parallel_tool_calls:
            for tool_call in parallel_call.tool_calls:
                print(tool_call.function.name)
                selected_tools.append({
                    "name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                })
    else:
        # Text response (when content is not None)
        selected_tools = response.choices[0].message.content
    
    return {"response": selected_tools}


if __name__ == "__main__":
    uvicorn.run("tool_selector_agent:app", host="0.0.0.0", port=8080, reload=True)