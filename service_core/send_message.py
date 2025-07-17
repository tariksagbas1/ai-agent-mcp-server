import json
from config import load_services
from router import resolve
from rpc_client import rpc_call
from produced import send_produced
import handlers

def send_message(message: dict, idep_dir: str):
    """
    message: {
        "service_filename": str,
        "service_code": str,
        "message_code": str,
        "payload": dict
    }
    """
    service_list = load_services(message["service_filename"], idep_dir)
    metadata = resolve(service_list, message["message_code"], message["service_code"])

    if metadata["message_type"].name == "RPC_CLIENT":
        return rpc_call(message, idep_dir)
    elif metadata["message_type"].name == "PRODUCED":
        return send_produced(message, idep_dir)
    else:
        raise ValueError(f"Unsupported message type: {metadata['message_type']}")