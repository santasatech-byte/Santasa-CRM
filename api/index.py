import os
import sys
import traceback

# Add all potential paths
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
backend_dir = os.path.join(root_dir, "hospital_crm", "backend")

for p in [backend_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    try:
        from app.main import app
    except Exception:
        from hospital_crm.backend.app.main import app
except Exception as e:
    err_trace = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI(title="Santasa CRM Diagnostic")
    
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def debug_error(full_path: str):
        return JSONResponse(
            status_code=500,
            content={
                "status": "startup_diagnostic",
                "error": str(e),
                "traceback": err_trace.splitlines(),
                "sys_path": sys.path
            }
        )
