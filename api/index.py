import os
import sys

# Ensure backend directory is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(root_dir, "hospital_crm", "backend")

for p in [root_dir, backend_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI(title="Santasa CRM API Fallback")
    
    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def fallback(path_name: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Serverless Backend Initialization Error",
                "detail": str(e),
                "hint": "Check Vercel Environment Variables: DATABASE_URL, SUPABASE_URL, SECRET_KEY."
            }
        )
