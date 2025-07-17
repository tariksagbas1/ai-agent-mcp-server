import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import handlers

# from bootstrap import bootstrap

# bootstrap("Test_Cakar", "LLM", "idep")

from bootstrap import bootstrap

if __name__ == "__main__":
    bootstrap()
