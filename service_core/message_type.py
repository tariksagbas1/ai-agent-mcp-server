from enum import Enum

class MessageType(Enum):
    PRODUCED = "produced"
    CONSUMED = "consumed"
    RPC_CLIENT = "rpc_client"
    RPC_SERVER = "rpc_server"