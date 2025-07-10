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
import pandas as pd
#from setup import icron_data_extract

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
    

mcp = FastMCP(name="Icron MCP Server", stateless_http=True, instructions="This is a simple MCP server that serves the Icron company.")

mcp.add_middleware(LoggingMiddleware())

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

@mcp.tool()
async def pick_tools(user_prompt: str) -> dict:
    """
    IMPORTANT: You must call this tool before using any other tool. Use the tools returned by this tool for the rest of the session.
    Returns the tools that you will be using to satisfy the user's request
    """
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    all_tools = await mcp.get_tools()

    tool_list_str = "\n".join([f"{name}: {tool.description}" for i, (name, tool) in enumerate(all_tools.items())])
    system_prompt = f"""You are a tool selector. Here are the available tools:\n{tool_list_str}\n"""
    user_message = f"Given the user query: \"{user_prompt}\"\nSelect all tools that are necessary to satisfy the user's request. Reply with the tool names separated by commas."

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0
    )

    selected_tools = response.choices[0].message.content
    selected_tools = [item.strip() for item in selected_tools.split(",")]

    if "pick_tools" in selected_tools:
        selected_tools.remove("pick_tools")
    print("SELECTED TOOLS ARE :", selected_tools)
    return {"result": json.dumps(selected_tools)}




if __name__ == "__main__":

    mcp.run(transport="http", port=8000, log_level="debug")


