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

def start_rpc_consumer_mcp(queue, host, port, username, password, virtual_host, all_tools, all_resource_templates, mcp):
    def callback(ch, method, props, body):
        import asyncio
        try:
            message = None
            if isinstance(body, bytes):
                body = body.decode('utf-8')

            message = json.loads(body)
            
            logger.info(f"[RPC] Received message: {message}")

            

            incoming_message_type = str(props.type)

            if incoming_message_type == "query.tools":
                message_type = "response.query.tools"
                result = {"tools" : all_tools}

            elif incoming_message_type == "query.resource_templates":
                message_type = "response.query.resource_templates"
                result = {"response" : all_resource_templates}

            elif incoming_message_type == "command.call_tool":
                message_type = "response.command.call_tool"
                tool_name = message.get("name")
                arguments = message.get("arguments")
                try:
                    tool_object = asyncio.run(mcp.get_tool(tool_name))
                    response = asyncio.run(tool_object.run(arguments))
                    
                    result = {"structuredContent" : response.structured_content}
                except Exception as e:
                    logger.error(f"[RPC] Error calling tool: {e}")
                    return
            
            elif incoming_message_type == "command.read_resource_template":
                message_type = "response.command.read_resource_template"
                resource_template_name = message.get("name")
                arguments = message.get("arguments")
                try:
                    resource_template_object = asyncio.run(mcp.get_resource_template(f"resource://{resource_template_name}" + "/{scenario_code}/{username}"))
                    response = asyncio.run(resource_template_object.read(arguments))
                    result = {"response" : response}
                except Exception as e:
                    logger.error(f"[RPC] Error reading resource template: {e}")
                    return

            else:
                logger.error(f"[RPC] Invalid message type: {incoming_message_type}")
                return


            if not isinstance(props.reply_to, str):
                logger.error(f"[!] Invalid reply_to: {props.reply_to}")
                return

            
                
            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id,type=message_type,content_type="application/json", headers={"StatusCode" : 200}),
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
