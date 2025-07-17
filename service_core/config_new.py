import os
import json
from dotenv import load_dotenv

load_dotenv()

DEPLOYMENT_CODE = os.getenv("DEPLOYMENT_CODE")  
SERVICE_CODE    = os.getenv("SERVICE_CODE")      
IDEP_DIR        = "service_core/idep"

def load_services():
    idep_path = os.path.join(IDEP_DIR, f"{DEPLOYMENT_CODE}.idep")
    if not os.path.exists(idep_path):
        raise FileNotFoundError(f"Dosya bulunamadı: {idep_path}")
    with open(idep_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    services = all_data.get("Services", [])
    active_service = next((s for s in services if s.get("ServiceCode") == SERVICE_CODE), None)
    if not active_service:
        raise ValueError(f"ServiceCode '{SERVICE_CODE}' bulunamadı in {DEPLOYMENT_CODE}.idep")
    return active_service

def load_section(section_name: str):
    """
    İlk seviye section’ı getirir.
    Örnek: load_section("LLMServiceOptions")
    """
    svc = load_services()
    if section_name not in svc:
        raise KeyError(f"Section '{section_name}' bulunamadı.")
    section = svc[section_name]
    return section

def load_subsection(section_name: str, subsection_name: str):
    """
    load_section ile alınan section içinden alt bölümü getirir.
    - Eğer section bir dict ise doğrudan dict[subsection_name]
    - Eğer section bir list ise, listedeki her elemandan subsection_name’i alıp liste olarak döner.
    
    Örnek:
      load_subsection("LLMServiceOptions", "LLMCredentials")
      load_subsection("RPCMessages_Server", "InputQueues")
    """
    section = load_section(section_name)

    # dict olarak alt bölümü al
    if isinstance(section, dict):
        if subsection_name not in section:
            raise KeyError(f"Subsection '{subsection_name}' bulunamadı in '{section_name}'.")
        sub = section[subsection_name]
        return sub

    if isinstance(section, list):
        results = []
        for idx, item in enumerate(section):
            if not isinstance(item, dict):
                continue
            if subsection_name not in item:
                continue
            results.append(item[subsection_name])
        if not results:
            raise KeyError(f"Listede hiçbir elemanda '{subsection_name}' bulunamadı in '{section_name}'.")
        return results

    raise TypeError(f"Section '{section_name} → subtype alınamaz.")
