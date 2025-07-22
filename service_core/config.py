import os
import json
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
PROJECT_DIR = Path(__file__).resolve().parent.parent

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOYMENT_CODE = os.getenv("DEPLOYMENT_CODE")  
SERVICE_CODE    = os.getenv("SERVICE_CODE")      
IDEP_DIR = os.path.join(PROJECT_DIR, "configs")

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
    svc = load_services()
    if section_name not in svc:
        raise KeyError(f"Section '{section_name}' bulunamadı.")
    return svc[section_name]

def load_subsection(section_name: str, subsection_name: str):
    section = load_section(section_name)

    if isinstance(section, dict):
        if subsection_name not in section:
            raise KeyError(f"Subsection '{subsection_name}' bulunamadı in '{section_name}'.")
        return section[subsection_name]

    if isinstance(section, list):
        results = []
        for item in section:
            if isinstance(item, dict) and subsection_name in item:
                results.append(item[subsection_name])
        if not results:
            raise KeyError(f"Listede hiçbir elemanda '{subsection_name}' bulunamadı in '{section_name}'.")
        return results

    raise TypeError(f"Section '{section_name}' ne dict ne de list; alt bölüm alınamaz.")

def load_subsection_field(section_name: str, subsection_name: str, field_name: str, first_only: bool = True):
    """
    Örnek:
      load_subsection_field("LLMServiceOptions", "LLMCredentials", "APIKey")
      -> tek APIKey döner (first_only=True ise)
      -> tüm APIKey'leri liste olarak döner (first_only=False ise)
    """
    sub = load_subsection(section_name, subsection_name)

    if isinstance(sub, dict):
        if field_name not in sub:
            raise KeyError(f"'{field_name}' alanı bulunamadı in subsection.")
        return sub[field_name]

    if isinstance(sub, list):
        values = []
        for idx, element in enumerate(sub):
            if not isinstance(element, dict):
                continue
            if field_name not in element:
                raise KeyError(f"'{field_name}' alanı bulunamadı listede, eleman {idx}.")
            values.append(element[field_name])

        if first_only:
            return values[0]
        return values

    raise TypeError("Alttaki veri dict veya list değil.")

##README##
    # a=load_section("LLMServiceOptions")
    # b=load_subsection("LLMServiceOptions", "LLMCredentials")
    # c=load_subsection_field("LLMServiceOptions", "LLMCredentials", "APIKey")
    # d=load_subsection_field("LLMServiceOptions", "LLMCredentials", "APIKey", first_only=True)
    # print("Section:", a)
    # print("Subsection:", b)
    # print("Single Field:", c)
    # print("All Fields:", d)
##README##