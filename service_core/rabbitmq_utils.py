import pika
import os
from service_core.config import get_user_credentials

def get_connection_parameters(metadata: dict) -> pika.ConnectionParameters:

    username, password = get_user_credentials()
    credentials = pika.PlainCredentials(username, password)

    return pika.ConnectionParameters(
        host=metadata["host"],
        port=metadata["port"],
        virtual_host=metadata["vhost"],
        credentials=credentials
    )