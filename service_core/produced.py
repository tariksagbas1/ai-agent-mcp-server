import json
from service_core.logger import get_logger

logger = get_logger(__name__)
import pika
from service_core.rabbitmq_utils import get_connection_parameters
import time
from service_core.router import resolve
from service_core.config import load_services

def send_produced(message: dict, idep_dir: str, max_attempts=3, retry_interval=2):
    service_list = load_services(message["service_filename"], idep_dir)
    metadata = resolve(service_list, message["message_code"], message["service_code"])

    attempt = 1
    while attempt <= max_attempts:
        try:
            connection = pika.BlockingConnection(get_connection_parameters(metadata))
            channel = connection.channel()
            channel.basic_publish(
                exchange=metadata["exchange"],
                routing_key=metadata["routing_key"],
                body=json.dumps(message)
            )

            logger.info(f"[Produced] Sent → exchange='{metadata['exchange']}', routing_key='{metadata['routing_key']}'")
            connection.close()
            return {"status": "sent"}

        except Exception as e:
            logger.error(f"[Produced] Attempt {attempt} failed: {e}")
            attempt += 1
            if attempt <= max_attempts:
                time.sleep(retry_interval)
            else:
                raise Exception(f"[Produced] Failed after {max_attempts} attempts: {e}")
