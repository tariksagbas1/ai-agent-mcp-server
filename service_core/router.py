from service_core.config import load_services
from service_core.registry import get_handler
from service_core.executor import execute
from service_core.message_type import MessageType
from service_core.credentials import DEFAULT_USERNAME, DEFAULT_PASSWORD

def resolve(service_list, message_code, service_code, allow_only_sendable=False, prefer_server=False):
    """
    Public message_code (örneğin 'LLMChat') ver, tüm .idep taranır, hangi mesaj tipi olduğu bulunur
    ve exchange, routing_key, vhost, port gibi değerler çıkarılır.
    """
    service = next((s for s in service_list if s["ServiceCode"] == service_code), None)
    if not service:
        raise ValueError(f"Service '{service_code}' not found.")

    # Aranacak bölümler
    if prefer_server:
        sections = [("RPCMessages_Server", "RequestMessageCode")]
    else:
        sections = [
            ("RPCMessages_Client", "RequestMessageCode"),
            ("ProducedMessages", "MessageCode")
        ]

    for section, key_name in sections:
        for entry in service.get(section, []):
            if entry.get(key_name) != message_code:
                continue

            return {
                "exchange": entry.get("MBExchangeName", ""),
                "routing_key": next(iter(entry.get("RoutingKeyParameters", {}).values()), message_code),
                "host": entry.get("MBHost", "localhost"),
                #"host": "rabbitmq",
                "vhost": entry.get("MBVirtualHostName"),
                "port": entry.get("MBPort"),
                "username": entry.get("MBUserName", DEFAULT_USERNAME),
                "password": entry.get("MBPassword", DEFAULT_PASSWORD)
            }

    raise ValueError(f"Message code '{message_code}' not found in any supported sections.")
    service = next((s for s in service_list if s["ServiceCode"] == service_code), None)
    if not service:
        raise ValueError(f"Service code '{service_code}' not found.")

    # RPCMessages_Client için yukarıdan al
    default_host = service.get("MBHost", "localhost")
    default_vhost = service.get("MBVirtualHostName", "ahmet.cakar")
    default_port = service.get("MBPort", 5672)

    sections = [
        ("ProducedMessages", MessageType.PRODUCED, "MessageCode", False),
        ("ConsumedMessages", MessageType.CONSUMED, "MessageCode", True),
        ("RPCMessages_Client", MessageType.RPC_CLIENT, "RequestMessageCode", False),
        ("RPCMessages_Server", MessageType.RPC_SERVER, "RequestMessageCode", True),
    ]

    for section, msg_type, key, has_queue in sections:
        for entry in service.get(section, []):
            if entry.get(key) == message_code:
                if allow_only_sendable and msg_type not in [MessageType.PRODUCED, MessageType.RPC_CLIENT]:
                    raise ValueError(
                        f"'{message_code}' is of type '{msg_type.name}', which is not a sendable message type (only PRODUCED or RPC_CLIENT allowed)."
                    )

                if has_queue:
                    queue_info = entry["InputQueues"][0]
                    return {
                        "message_type": msg_type,
                        "queue": queue_info.get("MBQueueName"),
                        "exchange": entry.get("MBExchangeName", ""),
                        "routing_key": next(iter(entry.get("RoutingKeyParameters", {}).values()), message_code),
                        "host": queue_info.get("MBHost", default_host),
                        "vhost": queue_info.get("MBVirtualHostName", default_vhost),
                        "port": queue_info.get("MBPort", default_port),
                        "username": DEFAULT_USERNAME,
                        "password": DEFAULT_PASSWORD
                    }
                else:
                    # Client için: queue yok ama host/vhost yukarıdan alınır
                    return {
                        "message_type": msg_type,
                        "queue": None,
                        "exchange": entry.get("MBExchangeName", ""),
                        "routing_key": next(iter(entry.get("RoutingKeyParameters", {}).values()), message_code),
                        "host": default_host,
                        "vhost": default_vhost,
                        "port": default_port,
                        "username": DEFAULT_USERNAME,
                        "password": DEFAULT_PASSWORD
                    }

    raise ValueError(f"MessageCode '{message_code}' not found in service '{service_code}'")

def route_and_execute(message, idep_dir):
    services = load_services(message["service_filename"], idep_dir)
    meta = resolve(services, message["message_code"], message["service_code"])
    handler = get_handler(message["message_code"])
    return execute(handler, message["payload"])
