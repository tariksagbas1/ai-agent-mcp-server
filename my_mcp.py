import sys
sys.path.append("..") 
from fastmcp import FastMCP
from datetime import datetime
#import pytz
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
import openai
import pandas as pd
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_REGISTRY = {}
PYDANTIC_MODELS = {}
FUNCTION_SCHEMAS = {}

def create_dynamic_model(
    model_name: str,
    fields: Dict[str, Type],
    class_attr: Dict[str, Any] = None
) -> Type[BaseModel]:
    """
    Creates a Pydantic model dynamically with field aliases.
    
    Args:
        model_name: Name for the generated model class
        fields: Dictionary mapping space-separated field names to their types
        class_attr: Optional dictionary of space-separated class parameter names and values
    """
    # Convert fields to no-space names with aliases
    field_definitions = {}
    for field_name, field_type in fields.items():
        #no_space_name = remove_spaces(field_name)
        field_definitions[field_name] = (field_type, Field(..., alias=field_name))
    
    # Create the base model
    DynamicModel = create_model(
        model_name,
        **field_definitions
    )
    
    # Convert and add class params
    if class_attr:
        for param_name, param_val in class_attr.items():
            #no_space_name = remove_spaces(param_name)
            setattr(DynamicModel, param_name, param_val)
    
    return DynamicModel

def to_dict(instance):
    """Convert instance to dictionary with no spaces in keys."""
    return {**{remove_spaces(k): v for k, v in instance.model_dump(by_alias=True).items()}, 
            **{k: v for k, v in instance.__class__.__dict__.items() 
               if not (k.startswith('_') or callable(v) or isinstance(v, property) 
               or k in {'model_config', 'model_fields', 'model_computed_fields'})}}


def define_pydantic_model_for_db_schema(func_name, description, params, returns, **constants):
    params_ = {split_by_capitals(key): convert_to_builtin_type(item) for key, item in params.items()}
    constants_ = {split_by_capitals(key): item for key, item in constants.items()}

    model = create_dynamic_model(model_name=func_name, fields=params_, class_attr=constants_)

    
    outputs = {split_by_capitals(field_name): data_type for field_name, data_type in returns.items()}
    description += " Fields: " + str(list(outputs.keys()))

    #model.__doc__ =  description

    return model, description

def define_pydantic_model_for_func_schema(func_name, description, params, returns, constants=None):

    params_ = {split_by_capitals(key): convert_to_builtin_type(item) for key, item in params.items()}
    #constants_ = {split_by_capitals(key): item for key, item in constants.items()}
    if constants is not None:
        constants_ = {split_by_capitals(key): convert_to_builtin_type(item) for key, item in constants.items()}
        params_.update(constants_)

    model = create_dynamic_model(model_name=func_name, fields=params_, class_attr=None)

    
    outputs = {split_by_capitals(field_name): data_type for field_name, data_type in returns.items()}
    description += " Fields: " + str(list(outputs.keys()))

    #model.__doc__ =  description

    return model, description


def transform_table_schema(json_dict: dict) -> dict:
    result = {}

    for table_name, table_info in json_dict.items():
        function_name = f"Extract_{table_name}"
        description = f"Extracts '{split_by_capitals(table_name)}' table data."

        fields = table_info.get("Fields", {})
        primary_keys = table_info.get("PrimaryKeys", [])

        params = {key: fields[key] for key in primary_keys if key in fields}

        result[function_name] = {
            "description": description,
            "params": params,
            "returns": fields
        }

        # CLASS_FIELDS[table_name] = list(fields.keys())
    return result


def transform_tool_definitions(tool_definitions): 
    global PYDANTIC_MODELS, FUNCTION_SCHEMAS

    db_schemas = tool_definitions['DBSchemas']
    print("Transforming tool definitions...")

    system_prompt = tool_definitions.get('SystemPrompt', "## No additional instuctions. ## ")
    print("SystemPrompt:", system_prompt)
    
    #PYDANTIC_MODELS = {}
    call_defs = {}
    table_defs = {} # for programmer agent
    data_contexts = [] # for tool selector agent

    for table_def_dict in db_schemas:
        table_defs.update(table_def_dict)
        call_def = transform_table_schema(table_def_dict)
        call_defs.update(call_def)

    for func_name, call_definition in call_defs.items():
        pydantic_model, description = define_pydantic_model_for_db_schema(func_name, **call_definition)
        PYDANTIC_MODELS[func_name] = pydantic_model
        openai_tool = openai.pydantic_function_tool(pydantic_model, description=description)
        data_contexts.append(openai_tool)

    FUNCTION_SCHEMAS = tool_definitions['Functions']

    functions = []
    for func_name, call_definition in FUNCTION_SCHEMAS.items():
        pydantic_model, description = define_pydantic_model_for_func_schema(func_name, **call_definition)
        PYDANTIC_MODELS[func_name] = pydantic_model
        openai_tool = openai.pydantic_function_tool(pydantic_model, description=description)
        functions.append(openai_tool)

    return {"system_prompt":system_prompt, "functions": functions, "FUNCTION_SCHEMAS":FUNCTION_SCHEMAS, "data_contexts": data_contexts, "table_defs": table_defs, "PYDANTIC_MODELS": PYDANTIC_MODELS}



class LoggingMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        print("====== MCP TOOL CALL ======")
        #print("Tool Context \n", context)
        print("TOOL NAME IS :", context.message.name)
        print("TOOL ARGUMENTS ARE :", context.message.arguments)
        print("===========================")
        result = await call_next(context)
        return result


    # \"\"\"{tool_description}\"\"\"
    # kwargs = locals()
    # json_msg = get_message_json('{tool_name}', **kwargs)
    # result = external_function_call('{tool_name}', json_msg)
    # return result

# Helper Functions
def get_message_json(tool_name, **kwargs):
    # TODO: Implement this
    return json.dumps(kwargs)


def external_function_call(tool_name, **kwargs):
  
    global PYDANTIC_MODELS, FUNCTION_SCHEMAS

    def create_dict_for_icron_func_call(tool_choice, scenario_id):
        
        #func_name: str = tool_choice['name']
        func_name = tool_name

        model = PYDANTIC_MODELS[func_name]
        args = json.loads(tool_choice['arguments'])
        instance = model(**args)
        tool_choice_dict = to_dict(instance)
        call_definition = FUNCTION_SCHEMAS[func_name]
        
        icron_input = {}
        user_data = {}

        icron_func_name = func_name

        is_extract_call = func_name.startswith("Extract_")

        if is_extract_call:
            icron_func_name = func_name[len("Extract_"):] + "s"

        icron_input['ScenarioCode'] = scenario_id #user_query['scenario_id']
        icron_input['ParentClassName'] = "ICLSystemServer"
        icron_input['Expression'] = icron_func_name

        if 'constants' in call_definition:
            for key in call_definition['constants'].keys():
                icron_input[key] = tool_choice_dict[key]
        
        if not is_extract_call:
            for key in call_definition['params'].keys():
                if 'date' not in key.lower():
                    user_data[key] = tool_choice_dict[key]
                else:
                    # Parse the string into a datetime object
                    date_str= tool_choice_dict[key]
                    try:
                        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            
                    formatted_date = dt.strftime("%Y-%m-%dT%H:%M:%S")
                    user_data[key] = formatted_date

            icron_input['Arguments'] = json.dumps(user_data)

        return icron_input

    icron_func_call_input = create_dict_for_icron_func_call(kwargs, kwargs["scenario_code"])

    headers = {
        'FunctionName': tool_name
    } 

    message_code = tool_name 

    # Mesajı gönder
    response = rpc_call(
        message_code=message_code,
        payload=icron_func_call_input,
        headers = headers
    )

    return response

def get_data_message(table_name, **kwargs):
    # TODO: Implement this
    return json.dumps(kwargs)

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
        "FunctionName": "ExtractData"
    }  

    data = rpc_call("ExtractData", json_body, headers, 60)

    if (data):
        df = pd.DataFrame(data['Objects'])
        #rename_columns(df)
        for col in df.columns:
            if 'date' in col.lower() or 'time' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col])
                except:
                    pass

        return df

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
    json_msg = get_message_json('{tool_name}', **kwargs)
    result = external_function_call('{tool_name}', json_msg)
    return result
        """
        # Get the function executable
        namespace = {"get_message_json": get_message_json, "external_function_call": external_function_call} # Generate a namespace
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
        namespace = {"datetime": datetime, "get_data_message": get_data_message, "external_data_extract_call": external_data_extract_call} # Generate a namespace
        exec(function_code, namespace) # Save function definition to namespace
        resource_func = namespace[f"Extract_{table_name}"] # Point to the function definition

        #uri_params = "/".join([f"{{{field}}}" for field in fields.keys()])
        
        uri_params = "/".join([f"{{{arg}}}" for arg in ['scenario_code', 'username']])
        resource_uri = f"resource://Extract_{table_name}/{uri_params}"

        # Register the resource
        mcp.resource(resource_uri)(resource_func)


from context import *

def read_idep_config():

    deployment_config = get_deployment_config()

    service_code = get_service_code()
    deployment_code = get_deployment_code()

    username = f"{service_code}_0@{deployment_code}"
    password = f"{service_code}_0@{deployment_code}"

    set_rabbitmq_credentials(username, password)

    mb_queues = {}
    rpc_client_config = None
    llm_credentials = None
    llm_tools = None

    for service in deployment_config['Services']:
        if service['ServiceCode'] == service_code:
            for rpc_messages_server in service['RPCMessages_Server']:

                if rpc_messages_server["RequestMessageCode"] == "LLMChatRequest":
                    mb_queues["LLMChat"] = rpc_messages_server["InputQueues"]

                elif rpc_messages_server["RequestMessageCode"] == "InitializeLLMAgentRequest":
                    mb_queues["InitializeLLMAgent"] = rpc_messages_server["InputQueues"]

                elif rpc_messages_server["RequestMessageCode"] == "RemoveLLMAgentRequest":
                    mb_queues["RemoveLLMAgent"] = rpc_messages_server["InputQueues"]
            

            llm_credentials = service['LLMServiceOptions']["LLMCredentials"]

            llm_tools = service['LLMServiceOptions']["LLMTools"]

            rpc_client_config = service['RPCMessages_Client'][0]

            # Assuming only one LLM service config is available
            break

    set_config(mb_queues, rpc_client_config, llm_credentials, llm_tools)

    return mb_queues

if __name__ == "__main__":
    
    mcp = FastMCP(name="Icron MCP Server", stateless_http=True, instructions="This is a simple MCP server that serves the Icron company.")

    mcp.add_middleware(LoggingMiddleware())

    _ = read_idep_config()
    deployment_config = get_deployment_config()

    service_code = get_service_code()
    deployment_code = get_deployment_code()

    username = f"{service_code}_0@{deployment_code}"
    password = f"{service_code}_0@{deployment_code}"

    set_rabbitmq_credentials(username, password)

    api_key = get_llm_credentials()[0]['APIKey']
    tools = get_llm_tools()

    tranformed_tools = transform_tool_definitions(tools)

    register_tools_from_idep(mcp, tools['Functions'])
    register_resources_from_idep(mcp, tools['DBSchemas'])
    
   # print(tools['DBSchemas'])
    all_tools = asyncio.run(mcp.get_tools())
    print("Registered tools:", all_tools)
    all_resources = asyncio.run(mcp.get_resources())
    print("Registered resources:", all_resources)
    mcp.run(transport="http", port=8000, log_level="debug")


