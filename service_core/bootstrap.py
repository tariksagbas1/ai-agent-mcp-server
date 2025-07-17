import threading
import os
from dotenv import load_dotenv

from service_core.logger import get_logger
from service_core.config import load_services
from service_core.credentials import DEFAULT_USERNAME, DEFAULT_PASSWORD
from service_core.consumer import start_consumer
from service_core.rpc_server import start_rpc_consumer

logger = get_logger(__name__)


def bootstrap():
    load_dotenv()

    idep_dir = os.getenv("IDEP_DIR", "service_core/idep")
    
    service = load_services()  # config.py içindeki yeni versiyon tek bir service döndürüyor

    def launch_thread(func, **kwargs):
        t = threading.Thread(target=func, kwargs=kwargs, daemon=True)
        t.start()

    # Listen to ConsumedMessages
    for entry in service.get("ConsumedMessages", []):
        for q in entry.get("InputQueues", []):
            launch_thread(
                start_consumer,
                queue=q["MBQueueName"],
                host=q.get("MBHost", "localhost"),
                port=q.get("MBPort", 5672),
                username=DEFAULT_USERNAME,
                password=DEFAULT_PASSWORD,
                virtual_host=q.get("MBVirtualHostName", "/"),
                idep_dir=idep_dir
            )

    # Listen to RPCMessages_Server
    for entry in service.get("RPCMessages_Server", []):
        for q in entry.get("InputQueues", []):
            launch_thread(
                start_rpc_consumer,
                queue=q["MBQueueName"],
                host=q.get("MBHost", "localhost"),
                port=q.get("MBPort", 5672),
                username=DEFAULT_USERNAME,
                password=DEFAULT_PASSWORD,
                virtual_host=q.get("MBVirtualHostName", "/"),
            )

    logger.info("✅ All queues are now being listened to.")
    while True:
        pass  # Sonsuz dinleme

