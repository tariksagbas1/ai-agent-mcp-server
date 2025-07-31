import sys
sys.path.append("..") 
from fastmcp import FastMCP
from datetime import datetime
import json
import requests
import base64
from dotenv import load_dotenv
import os
import traceback
import asyncio
from supabase import create_client
from fastmcp.server.dependencies import get_http_headers, get_http_request
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.tools.tool import FunctionTool
from fastmcp.tools.tool import Tool
from datetime import datetime
from fastmcp.resources import FileResource
from pathlib import Path
from utils import *
from service_core.rpc_client import rpc_call
from context import *
from service_core.config import load_services
from fastmcp.client import Client
import pytz

import openai
import pandas as pd
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))




class LoggingMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        print("====== MCP TOOL CALL ======")
        #print("Tool Context \n", context)
        print("TOOL NAME IS :", context.message.name)
        print("TOOL ARGUMENTS ARE :", context.message.arguments)
        print("===========================")
        result = await call_next(context)
        return result


# Helper Functions
def external_function_call(tool_name, **kwargs):

    
    headers = {
        'FunctionName': tool_name
    } 

    message_code = tool_name 
    # Mesajı gönder
    response = rpc_call(
        message_code=message_code,
        payload=kwargs,
        headers = headers
    )
    
    
    print(f"[RPC] Tool Call Response : {response}")

    return response

def external_data_extract_call(table_name, **kwargs) -> pd.DataFrame:
    """
    Extracts data behind the system where users interact with it and ask some questions. It returns a pandas DataFrame.
    """
    
    json_body = {
        "ScenarioCode": kwargs["scenario_code"],
        "ParentClassName": "ICLSystemServer",
        "Expression": table_name+"s",
        "TimeFormat": "%Y-%m-%dT%H:%M:%S"
    }

    headers = {
        'api_type': 'restapi',
        'endpoint': '/icron_api/v1/extract',
        "query_parameters": f"?UserName={username}",
    }  

    data = rpc_call("ExtractData", json_body, headers, 60)

    if (data.get("Error")):
        return data

    if (data):
        df = pd.DataFrame(data.get('Objects'))
        #rename_columns(df)
        for col in df.columns:
            if 'date' in col.lower() or 'time' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col])
                except:
                    pass
        
        print(df.to_json(orient="records", force_ascii=False))

        return df.to_json(orient="records", force_ascii=False)

def param_to_python_type(param_type: str) -> str:
    if param_type == "string" or param_type == "text":
        return "str"
    elif param_type == "integer":
        return "int"
    elif param_type == "boolean":
        return "bool"
    elif param_type == "list" or param_type == "array":
        return "list"
    elif param_type == "dictionary":
        return "dict"
    elif param_type == "float" or param_type == "real":
        return "float"
    else:
        return param_type

def register_tools_from_idep(mcp: FastMCP, function_schemas: str):
    """
    Registers the tools from the IDEP file.
    """

    for tool_name, tool_dict in function_schemas.items():

        tool_description = tool_dict.get("description", "")
        tool_params = tool_dict.get("params", {})
        tool_returns = tool_dict.get("returns", {})
        tool_constants = tool_dict.get("constants", {})

        # Generate the function signature
        param_strs = []
        for param, typ in tool_params.items():
            param_strs.append(f"{param}: {param_to_python_type(typ)}")

        if tool_constants:
            for param, typ in tool_constants.items():
                param_strs.append(f"{param}: {param_to_python_type(typ)}")

        param_sig = ", ".join(param_strs)
        
        # Generate the function code
        function_code = f"""
def {tool_name}({param_sig}):
    \"\"\"{tool_description}\"\"\"
    kwargs = locals()
    result = external_function_call('{tool_name}', **kwargs)
    return result
        """
        # Get the function executable
        namespace = {"external_function_call": external_function_call} # Generate a namespace
        exec(function_code, namespace) # Save function definition to namespace
        tool_func = namespace[tool_name] # Point to the function definition

        
        output_schema = {
            "type": "object",
            "additionalProperties" : False,
            "properties": {
                # Filling this part dynamically
                #...
                #...
            }
            # "required": [] Used for non-default values
            }
        for param_name, param_type in tool_returns.items():
            if param_type == "list" or param_type == "array":
                output_schema["properties"][param_name] = {"type": "array"}
            else:
                output_schema["properties"][param_name] = {"type": param_type}
        
        # Register the tool
        mcp.tool(tool_func, output_schema=output_schema)

def register_resources_from_idep(mcp: FastMCP, db_schemas: str):
    """
    Registers the resources from the IDEP file.
    """

    for db_schema in db_schemas:
        table_name, table_json = next(iter(db_schema.items()))
        table_description : str = table_json.get("Description", "")
        primary_keys : list[str] = table_json.get("PrimaryKeys", [])
        fields : dict = table_json.get("Fields", {})

        # param_strs = []
        # for field_name, field_type in fields.items():
        #     param_strs.append(f"{field_name}: {param_to_python_type(field_type)}")

        # param_sig = ", ".join(param_strs)
        table_description += f"This function extracts data of {table_name} as pd.DataFrame. Primary keys: {', '.join(primary_keys)}. Fields: {', '.join(fields.keys())}."
        
        function_code = f"""
def Extract_{table_name}(scenario_code: str, username: str):
    \"\"\"{table_description}\"\"\"
    kwargs = locals()
    result = external_data_extract_call('{table_name}', **kwargs)
    return result
        """
        # Get the function executable
        namespace = {"datetime": datetime, "external_data_extract_call": external_data_extract_call} # Generate a namespace
        exec(function_code, namespace) # Save function definition to namespace
        resource_func = namespace[f"Extract_{table_name}"] # Point to the function definition
        
        uri_params = "/".join([f"{{{arg}}}" for arg in ['scenario_code', 'username']])
        resource_uri = f"resource://Extract_{table_name}/{uri_params}"

        # Register the resource
        mcp.resource(resource_uri)(resource_func)



mcp = FastMCP(name="Icron MCP Server", instructions="This is a simple MCP server that serves the Icron company.", stateless_http=True)

mcp.add_middleware(LoggingMiddleware())

service_code = get_service_code()
deployment_code = get_deployment_code()

username = f"{service_code}_0@{deployment_code}"
password = f"{service_code}_0@{deployment_code}"

set_rabbitmq_credentials(username, password)
mcp_service = load_services()
tools = mcp_service.get('LLMServiceOptions').get('LLMTools', None)

if not tools:
    raise ValueError("No tools found")

register_tools_from_idep(mcp, tools['Functions'])
register_resources_from_idep(mcp, tools['DBSchemas'])


all_tools = asyncio.run(mcp.get_tools())
all_resource_templates = asyncio.run(mcp.get_resource_templates())

transformed_resource_templates = []
for resource_template in list(all_resource_templates.values()):
    transformed_resource_templates.append({
        "name" : resource_template.name,
        "description" : resource_template.description,
        "inputSchema" : resource_template.parameters,
    })


transformed_tools = []
for tool in list(all_tools.values()):
    transformed_tools.append({
        "name" : tool.name,
        "description" : tool.description,
        "inputSchema" : tool.parameters,
    })
    
    


