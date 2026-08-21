import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend = os.path.join(_root, "hospital_crm", "backend")

for p in [_backend, _root]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.main import app
