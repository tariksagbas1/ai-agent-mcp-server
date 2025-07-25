import os
import json


DEPLOYMENT_CODE = os.getenv("DEPLOYMENT_CODE")

def get_username_password(deployment_code, idep_dir):
    idep_path = os.path.join(idep_dir, f"{deployment_code}.idep")
    if not os.path.exists(idep_path):
        raise FileNotFoundError(f"Dosya bulunamadı: {idep_path}")
    with open(idep_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    services = all_data.get("Services", [])
    mb = next((s for s in services if s.get("MessageBrokerOptions", None) is not None), None)
    if not mb:
        raise ValueError(f"Message Broker bulunamadı in {deployment_code}.idep")
    username = mb.get("MessageBrokerOptions", {}).get("AdminUser")
    password = mb.get("MessageBrokerOptions", {}).get("AdminPassword")
    if not username or not password:
        raise ValueError(f"Username or password bulunamadı in {deployment_code}.idep")
    return username, password


DEFAULT_USERNAME, DEFAULT_PASSWORD = get_username_password(deployment_code=DEPLOYMENT_CODE, idep_dir="configs")
