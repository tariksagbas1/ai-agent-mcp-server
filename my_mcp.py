
from fastapi import FastAPI
from fastmcp import FastMCP
from datetime import datetime
from openai import OpenAI
from postgrest import APIError
import pytz
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
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()

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
def get_message_json(tool_name, **kwargs):
    # TODO: Implement this
    return json.dumps(kwargs)

def external_function_call(tool_name, json_msg):
    # TODO: Implement this
    return {"IsFeasible": True}

def get_data_message(table_name, **kwargs):
    # TODO: Implement this
    return json.dumps(kwargs)

def external_data_extract_call(table_name, json_msg):
    # TODO: Implement this
    return {"result": json_msg}

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

def register_tools_from_idep(mcp: FastMCP, idep_file: str):
    """
    Registers the tools from the IDEP file.
    """
    with open(idep_file, "r") as file:
        function_jsons = json.load(file).get("LLMTools", {}).get("Functions", {})
    for tool_name, tool_json in function_jsons.items():

        tool_description = tool_json.get("description", "")
        tool_params = tool_json.get("params", {})
        tool_returns = tool_json.get("returns", {})
        tool_constants = tool_json.get("constants", {})


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

def register_resources_from_idep(mcp: FastMCP, idep_file: str):
    """
    Registers the resources from the IDEP file.
    """
    with open(idep_file, "r") as file:
        db_schemas = json.load(file).get("LLMTools", {}).get("DBSchemas", {})
    for db_schema in db_schemas:
        table_name, table_json = next(iter(db_schema.items()))
        table_description : str = table_json.get("Description", "")
        primary_keys : list[str] = table_json.get("PrimaryKeys", [])
        fields : dict = table_json.get("Fields", {})

        param_strs = []
        for field_name, field_type in fields.items():
            param_strs.append(f"{field_name}: {param_to_python_type(field_type)}")

        param_sig = ", ".join(param_strs)

        function_code = f"""
def {table_name}({param_sig}):
    \"\"\"{table_description}\"\"\"
    kwargs = locals()
    json_msg = get_data_message('{table_name}', **kwargs)
    result = external_data_extract_call('{table_name}', json_msg)
    return result
        """
        # Get the function executable
        namespace = {"datetime": datetime, "get_data_message": get_data_message, "external_data_extract_call": external_data_extract_call} # Generate a namespace
        exec(function_code, namespace) # Save function definition to namespace
        resource_func = namespace[table_name] # Point to the function definition

        uri_params = "/".join([f"{{{field}}}" for field in fields.keys()])
        resource_uri = f"resource://{table_name}/{uri_params}"

        # Register the resource
        mcp.resource(resource_uri)(resource_func)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],            
    allow_methods=["*"],          
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

mcp = FastMCP.from_fastapi(
    app,                    
    stateless_http=True,
    name="My MCP Server",
    instructions="…"
)

#mcp = FastMCP(name="Icron MCP Server", stateless_http=True, instructions="This is a simple MCP server that serves the Icron company.")

mcp.add_middleware(LoggingMiddleware())


path = Path("./info.txt").resolve()
if path.exists():
    # Use a file:// URI scheme
    readme_resource = FileResource(
        uri=f"file://{path.as_posix()}",
        path=path, # Path to the actual file
        name="info.txt",
        description="Gives information about Beykoz, Uskudar, Sancaktepe and their populations",
        mime_type="text/plain",
        tags={"info"}
    )
    mcp.add_resource(readme_resource)


@mcp.tool
def get_date_time(timezone: str = "Europe/Istanbul") -> dict:
    """
   
    Gets the current date and time in a given timezone. \n
    Args:
        timezone: Timezone name (eg. Europe/Istanbul, America/New_York, etc.)
        Defaults to Europe/Istanbul
    Returns:
        The current date and time in the given timezone as a JSON object.
    """
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        return {
            "result" : json.dumps({
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": now.strftime("%Z")
            })
        }
    except pytz.UnknownTimeZoneError:
        return {"result": json.dumps({"error": f"Unknown timezone: {timezone}"})}

@mcp.tool
def draft_mail(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
    """
    Generates a draft email. \n
    Args:
        to: The email address of the recipient
        subject: The subject of the email
        body: The body of the email
        cc: The email address of the carbon copy recipient
        bcc: The email address of the blind carbon copy recipient
    Returns:
        The draft email as a JSON object.
    """
    try:
        token_res = requests.post(
            url = "https://oauth2.googleapis.com/token",
            data = {
                "client_id": os.getenv("CLIENT_ID"),
                "client_secret": os.getenv("CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": os.getenv("REFRESH_TOKEN") 
            },
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        if not token_res.ok:
            raise Exception("Failed to refresh token")
        
        access_token = token_res.json().get("access_token")
        if not access_token:
            raise Exception("Failed to get access token")
        
        lines = [
            f"To: {to}",
            f"Cc: {cc}" if cc else "",
            f"Bcc: {bcc}" if bcc else "",
            f"Subject: {subject}",
            "",
            body
        ]
        # Filter out empty lines
        filtered_lines = list(filter(bool, lines))
        joined_lines = "\r\n".join(filtered_lines)

        # Encode Base64
        raw_bytes = joined_lines.encode("utf-8")
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8").rstrip("=")

        draft_res = requests.post(
            url = "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            data = json.dumps({
                "message": {
                    "raw": raw_b64
                }
            })
        )
        if not draft_res.ok:
            raise Exception(f"Failed to generate draft email, Status Code: {draft_res.status_code}, Response: {draft_res.text}")
        
        return {
            "result" : json.dumps({
                "To": to,
                "Subject": subject,
                "Body": body,
                "DraftId": draft_res.json()["id"]
            })
        }

    except Exception as e:
        traceback.print_exc()
        return {"result": json.dumps({"error": f"Error generating draft email: {e}"})}

@mcp.tool
def send_mail(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
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
    try:
        headers = get_http_headers()
        print(headers)
        token_res = requests.post(
            url = "https://oauth2.googleapis.com/token",
            data = {
                "client_id": os.getenv("CLIENT_ID"),
                "client_secret": os.getenv("CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": os.getenv("REFRESH_TOKEN") 
            },
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        if not token_res.ok:
            raise Exception("Failed to refresh token")
        
        access_token = token_res.json().get("access_token")
        if not access_token:
            raise Exception("Failed to get access token")
        
        lines = [
            f"To: {to}",
            f"Cc: {cc}" if cc else "",
            f"Bcc: {bcc}" if bcc else "",
            f"Subject: {subject}",
            "",
            body
        ]
        # Filter out empty lines
        filtered_lines = list(filter(bool, lines))
        joined_lines = "\r\n".join(filtered_lines)

        # Encode Base64
        raw_bytes = joined_lines.encode("utf-8")
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8").rstrip("=")

        send_res = requests.post(
            url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            data = json.dumps({
                    "raw": raw_b64
            })
        )
        if not send_res.ok:
            raise Exception(f"Failed to send email, Status Code: {send_res.status_code}, Response: {send_res.text}")
        
        return {
            "result" : json.dumps({
                "To": to,
                "Subject": subject,
                "Body": body,
                "MessageId": send_res.json()["id"]
            })
        }

    except Exception as e:
        traceback.print_exc()
        return {"result": json.dumps({"error": f"Error sending email: {e}"})}

@mcp.tool
def get_employees(full_name: str = "", department: str = "", gender: str = "", office: str = "", rank: str = "", office_days: list = [], only_count: bool = False, requested_info: list = ["name", "department", "gender", "office", "rank", "monday", "tuesday", "wednesday", "thursday", "friday"]) -> dict:
    """
    Get the employees in the company. Optionally filters by department, gender, office, rank, and day of the week.
    Args:
        full_name: The **full name** of the employee (e.g., "Tarık Sağbaş"). 
        department: The department of the employee
        gender: The gender of the employee
        office: The office of the employee
        rank: The rank of the employee
        office_days: The days of the week the employee works in the office (Monday, Tuesday, Wednesday, Thursday, Friday)
        requested_info: The information to be returned about the employees (name, department, gender, office, rank, monday, tuesday, wednesday, thursday, friday)
        only_count: Whether to return only the count of the employees or the employees with their attributes (True/False)
    Returns:
        The employees with their attributes as a JSON object.
    """
    try:
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise Exception("Missing SUPABASE_URL or SUPABASE_ANON_KEY in environment variables.")
        
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        
        selected_columns = ", ".join(info.strip() for info in requested_info)
        query = supabase.table("employees").select(selected_columns, count="exact")

        if full_name:
            query = query.eq("name", full_name.title().strip())
        if department:
            query = query.eq("department", department.capitalize())
        if gender:
            query = query.eq("gender", gender.capitalize())
        if office:
            query = query.eq("office", office.capitalize())
        if rank:
            query = query.eq("rank", rank.capitalize())
        if office_days:
            for day in office_days:
                query = query.eq(day.strip().lower(), True)
        
        
        try:
            response = query.execute()
            
        except APIError as e:
            raise Exception(f"Supabase query failed: {e.message}")

        if only_count:
            try:
                return {"result": json.dumps(response.count)}
            except Exception as e:
                print("ERROR IS :", e)
                return {"result": json.dumps({"error": f"Error getting employees: {e}"})}
        
        employees = {"count": response.count}
        for e in response.data:
            employees[e["name"]] = {}
            for info in requested_info:
                employees[e["name"]][info] = e[info]

        return {"result": json.dumps(employees)}
    except Exception as e:
        traceback.print_exc()
        return {"result": json.dumps({"error": f"Error getting employees: {e}"})}

    """
    Use this tool if you are not able to satisfy the user's request. This tool will prompt the programmer agent to help you.
    """
    payload = {
        "user_prompt": user_prompt
    }
    
    resp = requests.post(
        "http://127.0.0.1:8000/test",
        json=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    )
    return {"result": json.dumps("asd")}


if __name__ == "__main__":
    register_tools_from_idep(mcp, "config/test_config.idep")
    register_resources_from_idep(mcp, "config/test_config.idep")
    all_tools = asyncio.run(mcp.get_tools())
    
    """
    for t in all_tools:
        print("*"*100)
        print(t)
        print("*"*100)
        print(all_tools[t])
        print("*"*100)
    """


    
    mcp.run(transport="http", port=8000, log_level="debug", host="0.0.0.0")


