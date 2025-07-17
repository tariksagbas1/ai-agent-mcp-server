import os
import json
from dotenv import load_dotenv

load_dotenv()

DEPLOYMENT_CODE = os.getenv("DEPLOYMENT_CODE")  
SERVICE_CODE = os.getenv("SERVICE_CODE")      
IDEP_DIR = "service_core/idep"

def load_services():
    idep_path = os.path.join(IDEP_DIR, f"{DEPLOYMENT_CODE}.idep")
    with open(idep_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    services = all_data.get("Services", [])
    active_service = next((s for s in services if s["ServiceCode"] == SERVICE_CODE), None)

    if not active_service:
        raise ValueError(f"ServiceCode '{SERVICE_CODE}' not found in {DEPLOYMENT_CODE}.idep")

    return active_service
