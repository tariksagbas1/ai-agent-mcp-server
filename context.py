
import os
import pika
import json 
from dotenv import load_dotenv


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

def get_deployment_code():
    global _deployment_code
    load_dotenv()
    _deployment_code = os.getenv("DEPLOYMENT_CODE")
    if not _deployment_code:
        raise EnvironmentError("DEPLOYMENT_CODE is not set in environment variables.")
    return _deployment_code
    
def get_service_code():
    global _service_code
    _service_code = os.getenv("SERVICE_CODE")
    if not _service_code:
        raise EnvironmentError("SERVICE_CODE is not set in environment variables.")
    return _service_code

def get_deployment_config():
    global _deployment_config
    if _deployment_config is not None:
        return _deployment_config

    idep_path = os.path.join(CURRENT_DIR, "configs", f"{get_deployment_code()}.idep")

    try:
        with open(idep_path, "r") as f:
            _deployment_config = json.load(f)
            print(f"Found deployment config file: {idep_path}")
            return _deployment_config
    except FileNotFoundError:
        raise FileNotFoundError(f"Deployment config file not found: {idep_path}")
    
def set_config(mb_queues, rpc_client_config, llm_credentials, llm_tools):
    global _mb_queues, _rpc_client_config, _llm_credentials, _llm_tools
    _mb_queues = mb_queues
    _rpc_client_config = rpc_client_config
    _llm_credentials = llm_credentials
    _llm_tools = llm_tools

def get_llm_tools():
    return _llm_tools

def get_llm_credentials():
    return _llm_credentials

def get_rpc_client_config():
    return _rpc_client_config

def get_mb_queues():
    return _mb_queues

def set_rabbitmq_credentials(username, password):
    global _rabbitmq_user, _rabbitmq_pass
    _rabbitmq_user = username
    _rabbitmq_pass = password
    print(f"RabbitMQ credentials have been configured. Username: {get_rabbitmq_user()}, Password: {get_rabbitmq_pass()}.")

def get_rabbitmq_user():
    return _rabbitmq_user

def get_rabbitmq_pass():
    return _rabbitmq_pass

def get_rabbitmq_connection(host, vhost, port):

    username = get_rabbitmq_user()
    password = get_rabbitmq_pass()

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
