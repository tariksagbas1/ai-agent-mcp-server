
import os
import json
import uuid
import pika
from dotenv import load_dotenv
from service_core.config import load_services, load_service_config
from service_core.router import resolve
from service_core.rabbitmq_utils import get_connection_parameters
from service_core.logger import get_logger
from typing import Any

logger = get_logger(__name__)
load_dotenv()

def rpc_call(message_code: str, payload: dict, headers:dict, service_code:str, timeout=5) -> dict[str, Any]:
    
    service = load_service_config()
    
    metadata = resolve([service], message_code, os.getenv("SERVICE_CODE"), prefer_server=False)
    
    connection = pika.BlockingConnection(get_connection_parameters(metadata))
    channel = connection.channel()

    result = channel.queue_declare(queue='', exclusive=True)
    callback_queue = result.method.queue
    correlation_id = str(uuid.uuid4())

    response = {}

    def on_response(ch, method, props, body):
        if props.correlation_id == correlation_id:
            response["body"] = json.loads(body)
            ch.stop_consuming()

    channel.basic_consume(queue=callback_queue, on_message_callback=on_response, auto_ack=True)

    exchange = metadata["exchange"] or ""
    routing_key = metadata["routing_key"]

    logger.info(f"📨 Sending RPC to → exchange='{exchange}' | routing_key='{routing_key}'")

    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        properties=pika.BasicProperties(
            reply_to=callback_queue,
            correlation_id=correlation_id,
            headers=headers
        ),
        body=json.dumps(payload)
    )

    channel.start_consuming()
    connection.close()

    return response.get("body", "No response received.")

def rpc_call_mcp(message_code: str, payload: dict, headers:dict, message_type : str ,timeout=20):
    
    service = load_service_config()
    metadata = resolve([service], message_code, os.getenv("SERVICE_CODE"), prefer_server=False)
  
    connection = pika.BlockingConnection(get_connection_parameters(metadata))
    channel = connection.channel()

    result = channel.queue_declare(queue='testreplyqueue', exclusive=True)
    callback_queue = result.method.queue
    correlation_id = str(uuid.uuid4())

    response = {}

    def on_response(ch, method, props, body):
        if props.correlation_id == correlation_id:
            response["body"] = json.loads(body)
            response["props"] = props
            ch.stop_consuming()

    channel.basic_consume(queue=callback_queue, on_message_callback=on_response, auto_ack=True)

    logger.info(f"📨 Sending RPC to → exchange={metadata.get('exchange')} | routing_key={metadata.get('routing_key')}")

    channel.basic_publish(
        exchange=metadata.get("exchange"), # type: ignore
        routing_key=metadata.get("routing_key"), # type: ignore
        properties=pika.BasicProperties(
            reply_to=callback_queue,
            correlation_id=correlation_id,
            headers=headers,
            type=message_type,
        ),
        body=json.dumps(payload)
    )

    channel.start_consuming()
    connection.close()

    return response


      