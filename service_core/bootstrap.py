import threading
import os
from dotenv import load_dotenv
import json

from service_core.logger import get_logger
from service_core.config import load_services
from service_core.credentials import DEFAULT_USERNAME, DEFAULT_PASSWORD

from service_core.rpc_server import start_rpc_consumer, start_rpc_consumer_mcp

DEPLOYMENT_CODE = os.getenv("DEPLOYMENT_CODE")
SERVICE_CODE = os.getenv("SERVICE_CODE")

logger = get_logger(__name__)

def get_service_dict(service_code, deployment_code, idep_dir):
    idep_path = os.path.join(idep_dir, f"{deployment_code}.idep")
    if not os.path.exists(idep_path):
        raise FileNotFoundError(f"Dosya bulunamadı: {idep_path}")
    with open(idep_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    services = all_data.get("Services", [])
    active_service = next((s for s in services if s.get("ServiceCode") == service_code), None)
    if not active_service:
        raise ValueError(f"ServiceCode '{service_code}' bulunamadı in {deployment_code}.idep")
    return active_service

def bootstrap_mcp(mcp, all_tools, all_resource_templates):
  load_dotenv()

  #service = get_service_dict(service_code=SERVICE_CODE, deployment_code=DEPLOYMENT_CODE, idep_dir="configs")
  service = load_services()
  def launch_thread(func, **kwargs):
      t = threading.Thread(target=func, kwargs=kwargs, daemon=True)
      t.start()

    # Listen to RPCMessages_Server
  for entry in service.get("RPCMessages_Server", []):
      for q in entry.get("InputQueues", []):
          launch_thread(
              start_rpc_consumer_mcp,
              all_tools=all_tools,
              all_resource_templates=all_resource_templates,
              mcp=mcp,
              queue=q["MBQueueName"],
              host=q.get("MBHost", "localhost"),
              #host="rabbitmq",
              port=q.get("MBPort", 5672),
              username=DEFAULT_USERNAME,
              password=DEFAULT_PASSWORD,
              virtual_host=q.get("MBVirtualHostName", "/"),
          )

  print("✅ All queues are now being listened to.")

  mcp.run(transport="http", port=8000, log_level="debug", host="0.0.0.0")

