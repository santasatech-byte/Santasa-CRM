"""
Hospital CRM - Main Application Factory
Configures FastAPI app, lifespan context, security middleware, exception handlers,
and registers all domain modules.
"""
from contextlib import asynccontextmanager
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import logger
from app.core.errors import CRMException, crm_exception_handler, generic_exception_handler
from app.core.database import Base, engine
from app.workers.scheduler import task_queue, scheduler_engine

# Import Domain Routers
from app.modules.core.router import router as core_router
from app.modules.administration.auth_router import router as auth_router
from app.modules.administration.hospital_router import router as hospital_router
from app.modules.administration.executive_router import router as executive_router
from app.modules.leads.router import router as leads_router
from app.modules.calls.router import router as telephony_router
from app.modules.calls.mobile_sync_router import router as mobile_sync_router
from app.modules.followups.router import router as followups_router
from app.modules.appointments.router import router as appointments_router
from app.modules.reports.router import router as reports_router
from app.modules.communication.router import router as communication_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and graceful shutdown."""
    import os
    logger.info(f"Starting {settings.APP_NAME} in [{settings.APP_ENV}] mode...")
    
    # Create DB tables if not exist
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"Database connection initialization note: {e}")
    
    # Only start persistent background worker threads in standalone/daemon mode (skip in serverless)
    is_serverless = os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("SERVERLESS")
    if not is_serverless:
        try:
            task_queue.start()
            scheduler_engine.start()
            logger.info("Application background worker threads initialized.")
        except Exception as e:
            logger.warning(f"Scheduler worker startup note: {e}")
    
    yield
    
    # Graceful shutdown
    if not is_serverless:
        try:
            await scheduler_engine.stop()
            await task_queue.stop()
            logger.info("Application shutdown complete.")
        except Exception as e:
            logger.warning(f"Shutdown cleanup note: {e}")


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Hospital Lead, Call Recording & Follow-up CRM API Engine",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Security & CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID and Performance Middleware
    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(duration)
        
        # Security response headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response

    # Exception Handlers
    app.add_exception_handler(CRMException, crm_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Root Health Ping
    @app.get("/api", tags=["Health"])
    @app.get("/api/health", tags=["Health"])
    @app.get("/api/v1/health", tags=["Health"])
    async def root_health():
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "env": settings.APP_ENV,
            "version": "1.0.0"
        }

    # Register Domain Modules
    app.include_router(core_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(hospital_router, prefix="/api/v1")
    app.include_router(executive_router, prefix="/api/v1")
    app.include_router(leads_router, prefix="/api/v1")
    app.include_router(telephony_router, prefix="/api/v1")
    app.include_router(mobile_sync_router, prefix="/api/v1")
    app.include_router(followups_router, prefix="/api/v1")
    app.include_router(appointments_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(communication_router, prefix="/api/v1")

    # ---------------------------------------------------------
    # Frontend SPA & Static Assets Serving (Vercel & Monolith)
    # ---------------------------------------------------------
    import os
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, JSONResponse

    base_dirs = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dist")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")),
    ]

    frontend_dist = next((d for d in base_dirs if os.path.exists(d) and os.path.exists(os.path.join(d, "index.html"))), None)

    if frontend_dist:
        assets_dir = os.path.join(frontend_dist, "assets")
        if os.path.exists(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="static-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
                return JSONResponse(status_code=404, content={"detail": "API endpoint not found"})
            
            target_file = os.path.join(frontend_dist, full_path)
            if full_path and os.path.exists(target_file) and os.path.isfile(target_file):
                return FileResponse(target_file)
            
            return FileResponse(os.path.join(frontend_dist, "index.html"))
    else:
        @app.get("/", include_in_schema=False)
        async def root_fallback():
            return {
                "status": "online",
                "app": settings.APP_NAME,
                "api_docs": "/docs",
                "message": "Santasa IVF CRM Backend Engine is live and operating."
            }

    return app


app = create_app()
