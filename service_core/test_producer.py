from produced import send_produced

message = {
    "service_filename": "Test_Cakar",
    "service_code": "LLM",
    "message_code": "ETL",
    "payload": {"foo": "bar"}
}

response = send_produced(message, idep_dir="idep")
print(response)
