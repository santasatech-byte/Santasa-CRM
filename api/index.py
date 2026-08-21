import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(root_dir, "hospital_crm", "backend")

for p in [backend_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.main import app
