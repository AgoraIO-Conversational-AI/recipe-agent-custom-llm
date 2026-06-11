import os
import sys

_LLM_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _LLM_SRC not in sys.path:
    sys.path.insert(0, _LLM_SRC)
