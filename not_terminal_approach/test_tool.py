import subprocess
import threading
import queue

class RSession:
    def __init__(self, script_path):
        # start R in “slave” mode (no prompts, no GUI)
        self.proc = subprocess.Popen(
            ["R", "--slave"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        # load your R file once
        self._run(f"source('{script_path}')")

    def _run(self, cmd):
        """Send one command and read exactly one line back."""
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()
        return self.proc.stdout.readline().strip()

    def call(self, func_name, *args):
        
        arg_list = ",".join(map(repr, args))
        return self._run(f"cat({func_name}({arg_list}), '\\n')")

    def close(self):
        self.proc.stdin.write("q('no')\n")
        self.proc.stdin.flush()
        self.proc.wait()

# usage
if __name__ == "__main__":
    r = RSession("test_tool.r")     
    print(r.call("myfunc", 21, 20, 40, 50)) 
    print(r.call("myfunc", 10)) 
    r.close()