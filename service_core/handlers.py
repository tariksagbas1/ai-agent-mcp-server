from registry import register

@register("LLMChat")
def add(a, b):
    return a + b

@register("InitializeLLMAgentRequest")
def add(a, b):
    return a - b
