import sys
sys.path.append(".")
sys.path.append("..")
import threading
import os

import argparse
from dotenv import load_dotenv
import json
from pathlib import Path
from service_core.logger import get_logger
from service_core.config import load_services, load_service_config, get_user_credentials

from service_core.rpc_server import start_rpc_consumer, start_rpc_consumer_mcp
from icron_mcp.app import main as mcp_main

load_dotenv()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = Path(__file__).resolve().parent.parent    
IDEP_DIR = os.path.join(PROJECT_DIR, "configs")

logger = get_logger(__name__)

def get_thread(func, **kwargs):
    return threading.Thread(target=func, kwargs=kwargs, daemon=True)

def bootstrap():

    service = load_service_config()
    username, password = get_user_credentials()

    threads = []
    # for entry in service.get("ProducedMessages", []):
    #     for q in entry.get("InputQueues", []):
    #         t = get_thread(
    #             start_rpc_consumer,
    #             queue=q["MBQueueName"],
    #             host=q.get("MBHost", "localhost"),
    #             port=q.get("MBPort", 5672),
    #             username=username,
    #             password=password,
    #             virtual_host=q.get("MBVirtualHostName", "/"),
    #             #idep_dir=IDEP_DIR
    #         )
    #         threads.append(t)

    # Listen to ConsumedMessages
    for entry in service.get("ConsumedMessages", []):
        for q in entry.get("InputQueues", []):
            t = get_thread(
                start_rpc_consumer,
                queue=q["MBQueueName"],
                host=q.get("MBHost", "localhost"),
                port=q.get("MBPort", 5672),
                username=username,
                password=password,
                virtual_host=q.get("MBVirtualHostName", "/"),
            )
            threads.append(t)
    
    logger.info("✅ All queues are now being listened to.")

    for t in threads:
        t.start()

    for t in threads:
        t.join()

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

def bootstrap_mcp():

    mcp_server, all_tools, all_resource_templates = mcp_main()
    service = load_service_config()
    username, password = get_user_credentials()
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
                mcp=mcp_server,
                queue=q["MBQueueName"],
                host=q.get("MBHost", "localhost"),
                port=q.get("MBPort", 5672),
                username=username,
                password=password,
                virtual_host=q.get("MBVirtualHostName", "/"),
            )

    print("✅ All queues are now being listened to.")

    mcp_server.run(transport="http", port=8000, log_level="debug", host="0.0.0.0")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run a specific task.")
    parser.add_argument("--task", default="llm", help="Name of the task to run")

    args = parser.parse_args()

    # You can add conditional logic here
    if args.task == "llm":
        bootstrap()
    elif args.task == "mcp":
        bootstrap_mcp()
    else:
        print(f"Unknown task: {args.task}")
        sys.exit(1)


