import os
import sys
import traceback
import uvicorn

# Add backend directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from app.main import app
except Exception as e:
    print("FATAL STARTUP IMPORT ERROR:")
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting Santasa CRM Production Engine on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
