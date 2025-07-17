import os
from dotenv import load_dotenv
from send_message import send_message
from rpc_client import rpc_call

# Ortam değişkenlerini yükle
load_dotenv()

# Gerekli .env değişkenleri
message_code = "InitializeLLMAgentRequest"  # İstediğin mesaj kodu
payload = {
    "a": 10,
    "b": 150
}

# Mesajı gönder
response = rpc_call(
    message_code=message_code,
    payload=payload
)

print("✅ Returned Value:", response)
