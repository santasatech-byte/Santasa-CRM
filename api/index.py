import os
import sys

_api_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_api_dir)

for p in [_api_dir, _root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from api.app.main import app
