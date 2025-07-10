import os
import json
import time
from typing import Any, Dict, Optional
import uuid
import numpy as np
import pika
import threading
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

_mb_queues = None
_rpc_client_config = None
_llm_credentials = None
_llm_tools = None
_deployment_config = None
_rabbitmq_user = None
_rabbitmq_pass = None
_service_code = None
_deployment_code = None

def get_deployment_config():
    global _deployment_config
    if _deployment_config is not None:
        return _deployment_config

    idep_path = os.path.join(CURRENT_DIR, "config", "config.idep")

    try:
        with open(idep_path, "r") as f:
            _deployment_config = json.load(f)
            print(f"Found deployment config file: {idep_path}")
            return _deployment_config
    except FileNotFoundError:
        raise FileNotFoundError(f"Deployment config file not found: {idep_path}")


def set_rabbitmq_credentials(username, password):
    global _rabbitmq_user, _rabbitmq_pass
    _rabbitmq_user = username
    _rabbitmq_pass = password
    print(f"RabbitMQ credentials have been configured. Username: platform, Password: platform")

def set_config(mb_queues, rpc_client_config, llm_credentials, llm_tools):
    global _mb_queues, _rpc_client_config, _llm_credentials, _llm_tools
    _mb_queues = mb_queues
    _rpc_client_config = rpc_client_config
    _llm_credentials = llm_credentials
    _llm_tools = llm_tools

def read_idep_config():

    deployment_config = get_deployment_config()

    service_code = "LLM"
    deployment_code = "config"

    username = f"{service_code}_0@{deployment_code}"
    password = f"{service_code}_0@{deployment_code}"

    set_rabbitmq_credentials("platform", "platform")

    mb_queues = {}
    rpc_client_config = None
    llm_credentials = None
    llm_tools = None

    for service in deployment_config['Services']:
        if service['ServiceCode'] == service_code:
            for rpc_messages_server in service['RPCMessages_Server']:

                if rpc_messages_server["RequestMessageCode"] == "LLMChatRequest":
                    mb_queues["LLMChat"] = rpc_messages_server["InputQueues"]

                elif rpc_messages_server["RequestMessageCode"] == "InitializeLLMAgentRequest":
                    mb_queues["InitializeLLMAgent"] = rpc_messages_server["InputQueues"]

                elif rpc_messages_server["RequestMessageCode"] == "RemoveLLMAgentRequest":
                    mb_queues["RemoveLLMAgent"] = rpc_messages_server["InputQueues"]
            

            llm_credentials = service['LLMServiceOptions']["LLMCredentials"]

            llm_tools = service['LLMServiceOptions']["LLMTools"]

            rpc_client_config = service['RPCMessages_Client'][0]

            # Assuming only one LLM service config is available
            break

    set_config(mb_queues, rpc_client_config, llm_credentials, llm_tools)

    return mb_queues




class RabbitMQRpcClient:
    """
    RabbitMQ RPC Client implementation using pika library.
    Handles asynchronous request-response pattern with timeout functionality.
    """
    
    def __init__(self, 
                 request_message_code: str,
                 response_message_code: str,
                 mb_deployment_code: str,
                 mb_service_code: str,
                 mb_virtual_host_name: str,
                 mb_exchange_name: str,
                 mb_host: str,
                 mb_port: int,
                 mb_username: str,
                 mb_password: str,
                 timeout_duration: int,
                 routing_key_parameters: Dict[str, Any]):
        """
        Initialize the RabbitMQ RPC client.
        
        Args:
            request_message_code (str): Code for request messages
            response_message_code (str): Code for response messages
            mb_deployment_code (str): Message broker deployment code
            mb_service_code (str): Message broker service code
            mb_virtual_host_name (str): Virtual host name
            mb_exchange_name (str): Exchange name
            mb_host (str): RabbitMQ host
            mb_port (int): RabbitMQ port
            timeout_duration (int): Timeout duration in seconds
            routing_key_parameters (Dict[str, Any]): Parameters for routing key
        """
        self.request_message_code = request_message_code
        self.response_message_code = response_message_code
        self.mb_deployment_code = mb_deployment_code
        self.mb_service_code = mb_service_code
        self.mb_virtual_host_name = mb_virtual_host_name
        self.mb_exchange_name = mb_exchange_name
        self.mb_host = mb_host
        self.mb_port = mb_port
        self.mb_username = mb_username
        self.mb_password = mb_password
        self.timeout_duration = timeout_duration
        self.routing_key_parameters = routing_key_parameters
        
        # Instance variables
        self.connection = None
        self.channel = None
        self.callback_queue = None
        self.response = None
        self.correlation_id = None
        self.response_received = False
        self.consumer_tag = None
        self._is_open = False
        self._lock = threading.Lock()
        
        # Set up the connection and channel
        self._setup()
    
    def _setup(self):
        """Set up the connection, channel, and callback queue."""
        try:
            # Create connection parameters
            credentials = pika.PlainCredentials(self.mb_username,  self.mb_password)
            parameters = pika.ConnectionParameters(
                host=self.mb_host,
                port=self.mb_port,
                virtual_host=self.mb_virtual_host_name,
                credentials=credentials
            )
            
            # Establish connection
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # # Declare exchange
            # self.channel.exchange_declare(
            #     exchange=self.mb_exchange_name,
            #     exchange_type='topic',
            #     durable=True
            # )
            
            # Declare callback queue
            result = self.channel.queue_declare(queue='', exclusive=True)
            self.callback_queue = result.method.queue
            
            # Set up consumer
            self.consumer_tag = self.channel.basic_consume(
                queue=self.callback_queue,
                on_message_callback=self._on_response,
                auto_ack=True
            )
            
            self._is_open = True
        except Exception as e:
            print(f"Error setting up RabbitMQ connection: {e}")
            self._is_open = False
            raise
    
    def _on_response(self, ch, method, props, body):
        """
        Callback function when a response is received.
        
        Args:
            ch: Channel
            method: Method
            props: Properties
            body: Message body
        """
        if self.correlation_id == props.correlation_id:
            with self._lock:
                self.response = body
                self.response_received = True
    
    def _generate_routing_key(self) -> str:
        # """
        # Generate routing key based on parameters.
        
        # Returns:
        #     str: Generated routing key
        # """
        # base_key = f"{self.request_message_code}.{self.mb_deployment_code}.{self.mb_service_code}"
        
        # # Add any additional routing key parameters if provided
        # if self.routing_key_parameters:
        #     for key, value in self.routing_key_parameters.items():
        #         if value:  # Only add non-empty values
        #             base_key += f".{value}"
        
        base_key = list(self.routing_key_parameters.values())[0]

        return base_key
    
    def call(self, message: Dict[str, Any], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Make an RPC call to the RabbitMQ server.
        
        Args:
            message (Dict[str, Any]): Message to be sent
            
        Returns:
            Optional[Dict[str, Any]]: Response message or None if timeout or error
        """
        if not self._is_open:
            self._setup()
        
        # Reset response variables
        self.response = None
        self.response_received = False
        
        # Generate unique correlation ID
        self.correlation_id = str(uuid.uuid4())
        
        # Create routing key
        routing_key = self._generate_routing_key() 
        
        try:
            # Send the message
            message_body = json.dumps(message)
            self.channel.basic_publish(
                exchange=self.mb_exchange_name,
                routing_key=routing_key,
                properties=pika.BasicProperties(
                    reply_to=self.callback_queue,
                    correlation_id=self.correlation_id,
                    headers=headers,
                    #content_type='application/json',
                    delivery_mode=2,  # Make message persistent
                ),
                body=message_body
            )
            
            # Wait for response with timeout
            print("--------------------------------")
            print(self.mb_exchange_name, routing_key)
            print(self.request_message_code)
            print(self.response_message_code)
            print(self.mb_deployment_code)
            print(self.mb_service_code)
            print(self.mb_virtual_host_name)
            print(self.mb_exchange_name)
            print(self.mb_host)
            start_time = time.time()
            while not self.response_received:
                # Process data events to trigger callbacks
                self.connection.process_data_events()
                
                # Check for timeout
                if time.time() - start_time > self.timeout_duration:
                    print(f"Request timed out after {self.timeout_duration} seconds")
                    return None
                
                # Short sleep to avoid busy waiting
                time.sleep(0.01)
            
            # Parse and return the response
            if self.response:
                return json.loads(self.response)
            
            return None
        except Exception as e:
            print(f"Error during RPC call: {e}")
            return None
    
    def close(self):
        """Close the connection to RabbitMQ."""
        if self.channel and self.channel.is_open:
            if self.consumer_tag:
                self.channel.basic_cancel(self.consumer_tag)
            self.channel.close()
        
        if self.connection and self.connection.is_open:
            self.connection.close()
        
        self._is_open = False

def get_rpc_client():

    read_idep_config()
    config = _rpc_client_config

    if config is None:
        raise ValueError("rpc_client_config is not loaded. Make sure read_idep_config() was called and service or message broker user with given code exists.")

    rpc_client = RabbitMQRpcClient(
        request_message_code=config['RequestMessageCode'],
        response_message_code=config.get('ResponseMessageCode', ""),
        mb_deployment_code=config['MBDeploymentCode'],
        mb_service_code=config['MBServiceCode'],
        mb_virtual_host_name=config['MBVirtualHostName'],
        mb_exchange_name=config.get('MBExchangeName', ""),
        mb_host=config['MBHost'],
        mb_port=config['MBPort'],
        mb_username = _rabbitmq_user,
        mb_password = _rabbitmq_pass,
        timeout_duration=config.get('TimeoutDuration', 60),
        routing_key_parameters=config['RoutingKeyParameters']
    )
    return rpc_client


def icron_data_extract(json_body, headers):

    rpc_client = get_rpc_client()

    # TODO: check "error" in response
    response: Dict[str, Any] = rpc_client.call(json_body, headers)
    rpc_client.close()
    return response


def extract_data(table_name: str, username: str, scenario_code: str):
    """
    Extracts data behind the system where users interact with it and ask some questions. It returns a pandas DataFrame.
    """
    
    json_body = {
        "ScenarioCode": scenario_code,
        "ParentClassName": "ICLSystemServer",
        "Expression": table_name+"s",
        "TimeFormat": "%Y-%m-%dT%H:%M:%S"
    }

    print(">>>>>>>>>>>>>>>>", json_body)

    headers = {
        'api_type': 'restapi',
        'endpoint': '/icron_api/v1/extract',
        "query_parameters": f"?UserName={username}"
    }  

    data = icron_data_extract(json_body, headers)
    return data

print(extract_data("Inventory", "ahmet.cakar", "WFM"))

"""
def get_rabbitmq_connection(host, vhost, port):

    username = "platform"
    password = "platform"

    if not username or not password:
        raise EnvironmentError("RabbitMQ username or password not set.")

    credentials = pika.PlainCredentials(username=username, password=password)
    parameters = pika.ConnectionParameters(
        host=host,
        virtual_host=vhost,
        port=port,
        credentials=credentials,
        heartbeat=90
    )
    print(f"Getting rabbitmq connection: Host: {host}, Port: {port}, Vhost: {vhost}.")
    return pika.BlockingConnection(parameters)

def keep_connection_alive(connection):
    
    def keep_alive():
        
        try:
            connection.process_data_events()
            connection.call_later(30, keep_alive)
        
        except Exception as e:
            print(f"[!] Keep-alive failed: {e}")
    
    connection.call_later(30, keep_alive)

def request_handler(process_function: callable):

    def on_request(ch, method, props, body):

        print(f"Request received on queue: {method.routing_key}")
        print("Raw request body:", body)
        print("Request properties:", props)

        try:
            body = json.loads(body.decode("latin-1"))

            # Convert lists to numpy arrays if needed
            for key, val in body.items():
                if isinstance(val, list):
                    body[key] = np.array(val).ravel()

            response, status_code = process_function(body)

            response_json = json.dumps(response, ensure_ascii=False).encode("utf-8")

        except Exception:
            response = {
                "message": "Failed",
                "data_type": None,
                "data": None
            }
            status_code = 500
            response_json = json.dumps(response, ensure_ascii=False).encode("utf-8")
        
        # TODO: MBExchangeName
        ch.basic_publish(
            exchange='',
            routing_key=props.reply_to,
            properties=pika.BasicProperties(
                correlation_id=props.correlation_id,
                headers={'StatusCode': str(status_code)}
            ),
            body=response_json
        )

        truncated_response = json.dumps(response, ensure_ascii=False)[:100]
        print(f"Response sent: {truncated_response}")
        print(f"Routing key: {props.reply_to}, Correlation ID: {props.correlation_id}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[✓] Response acknowledged and sent for queue: {method.routing_key}")

    return on_request

def start_consumer(connection, queue_name, func):


    channel = connection.channel()
    #channel.queue_declare(queue=queue_name)

    channel.basic_qos(prefetch_count=1)

    on_request_func = request_handler(func)

    channel.basic_consume(queue=queue_name, on_message_callback=on_request_func)

    print(f"Awaiting requests at {queue_name}")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        connection.close()


mb_queues = read_idep_config()

for queue_type, queues in mb_queues.items():

    for queue_info in queues:
        conn = get_rabbitmq_connection(host = queue_info["MBHost"], vhost = queue_info["MBVirtualHostName"], port = queue_info["MBPort"])
        keep_connection_alive(conn)

        queue = queue_info["MBQueueName"]

  """      