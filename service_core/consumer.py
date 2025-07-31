# consumer.py
from service_core.logger import get_logger
logger = get_logger(__name__)
import pika
import json
#from service_core.router import route_and_execute
from service_core.rabbitmq_utils import get_connection_parameters

# def start_consumer(queue, host, port, username, password, virtual_host, idep_dir):
#     credentials = pika.PlainCredentials(username, password)
#     parameters = pika.ConnectionParameters(
#         host=host,
#         port=port,
#         virtual_host=virtual_host,
#         credentials=credentials
#     )
    
#     connection = pika.BlockingConnection(parameters)
#     channel = connection.channel()

#     def callback(ch, method, properties, body):
#         try:
#             message = json.loads(body)
#             logger.info(f"Received message: {message}")
#             result = route_and_execute(message, idep_dir)
#             logger.info(f"Handled result: {result}")
#         except Exception as e:
#             logger.error(f" Error processing message: {e}")

#     channel.basic_consume(queue=queue, on_message_callback=callback, auto_ack=True)
#     logger.info(f"Listening on queue '{queue}'...")
#     channel.start_consuming()
