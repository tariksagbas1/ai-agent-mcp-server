import pika
from service_core.credentials import DEFAULT_USERNAME, DEFAULT_PASSWORD

def get_connection_parameters(metadata: dict) -> pika.ConnectionParameters:
    credentials = pika.PlainCredentials(DEFAULT_USERNAME,DEFAULT_PASSWORD)
    return pika.ConnectionParameters(
        host=metadata["host"],
        port=metadata["port"],
        virtual_host=metadata["vhost"],
        credentials=credentials
    )