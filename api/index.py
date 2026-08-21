import os
import sys
import traceback

_api_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_api_dir)

for p in [_api_dir, _root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from api.app.main import app as main_app
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    
    class ErrorCatchMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            try:
                return await call_next(request)
            except Exception as exc:
                return JSONResponse(
                    status_code=500,
                    content={"error": str(exc), "trace": traceback.format_exc().splitlines()}
                )
    
    main_app.add_middleware(ErrorCatchMiddleware)
    app = main_app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI(title="Santasa CRM Diagnostic")
    err_msg = str(e)
    tb = traceback.format_exc().splitlines()
    
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def diag_route(full_path: str):
        return JSONResponse(
            status_code=500,
            content={"diagnostic_error": err_msg, "traceback": tb, "sys_path": sys.path}
        )
