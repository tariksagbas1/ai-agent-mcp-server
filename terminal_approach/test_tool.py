import subprocess

def call_myfunc(x):
    cmd = ["Rscript", "terminal_approach/test_tool.r", str(x)]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out.stdout

print(call_myfunc(21))  # → 42