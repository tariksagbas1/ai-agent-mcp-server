HANDLERS = {}

def register(code):
    def wrapper(func):
        HANDLERS[code] = func
        return func
    return wrapper

def get_handler(code):
    return HANDLERS.get(code)
