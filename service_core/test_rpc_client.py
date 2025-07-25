import os
from dotenv import load_dotenv
from service_core.send_message import send_message
from service_core.rpc_client import rpc_call_mcp

# Ortam değişkenlerini yükle
load_dotenv()

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
} 

# Mesajı gönder
"""
response = rpc_call_mcp(
    message_code = "MCP",
    payload = {
        "name": "OrderSimulation",
        "arguments": {
            'CustomerName': '123',
            'ItemName': '123',
            'Priority': 121,
            'Quantity': 123,
            'Date': '123',
            'LineStatus': '123',
            'ScenarioCode': '123',
            'UserName': '123',
            'InventoryCode': '123'
        }
    },
    headers=headers,
    message_type = "command.call_tool"
)
"""


response = rpc_call_mcp(
    message_code = "MCP",
    payload = {
        "name": "Extract_Inventory",
        "arguments": {
            "scenario_code": "ODP",
            "username": "furkan.canturk"
        }
    },
    headers=headers,
    message_type = "command.read_resource_template"
)

"""
response = rpc_call_mcp(
    message_code = "MCP",
    payload = {
        "name": "Extract_Inventory",
        "arguments": {
            "scenario_code": "ODP",
            "username": "furkan.canturk"
        }
    },
    headers=headers,
    message_type = "query.tools"
)
"""
print("✅ Returned Value:", response.get("body"))
props = response.get("props")
"""
for p in dir(props):
    if not p.startswith("__"):
        if hasattr(props, p):
            if getattr(props, p) is not None:
                print(p, getattr(props, p))
"""

