import pika
import json
import threading
from service_core.logger import get_logger
from service_core.router import resolve
from service_core.registry import get_handler
from service_core.executor import execute

logger = get_logger(__name__)

def start_rpc_consumer(queue, host, port, username, password, virtual_host):
    def callback(ch, method, props, body):
        try:
            message = json.loads(body)
            logger.info(f"[RPC] Received message: {message}")

            message_code = message.get("message_code")
            payload = message.get("payload")

            if not message_code or not payload:
                raise ValueError("Invalid message format. 'message_code' and 'payload' are required.")

            handler = get_handler(message_code)
            result = execute(handler, payload)

            if not isinstance(props.reply_to, str):
                logger.error(f"[!] Invalid reply_to: {props.reply_to}")
                return

            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id),
                body=json.dumps(result)
            )

        except Exception as e:
            logger.error(f"[RPC] Error processing message: {e}")

    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        virtual_host=virtual_host,
        credentials=credentials
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)

    channel.basic_consume(queue=queue, on_message_callback=callback, auto_ack=True)
    logger.info(f"[RPC] Listening on RPC queue '{queue}'...")

    channel.start_consuming()
