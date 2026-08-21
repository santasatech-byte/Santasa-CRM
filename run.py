import os
import sys
import traceback
import uvicorn

root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "hospital_crm", "backend")

for p in [backend_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.main import app
except Exception as e:
    print("FATAL STARTUP IMPORT ERROR AT ROOT:")
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting Santasa CRM Production Engine from root on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
