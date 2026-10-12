import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.api.routes_simulation import router as sim_router
from backend.app.api.routes_optimization import router as opt_router
from backend.app.api.routes_reports import router as rep_router

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smartflow.backend")

app = FastAPI(
    title="SmartFlow Traffic Simulation & Signal Optimization API",
    description="Internal optimization engine and authoritative traffic simulation backend.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(sim_router)
app.include_router(opt_router)
app.include_router(rep_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error handling {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An internal error occurred processing the simulation request.",
            "detail": str(exc) if settings.DEBUG else None,
            "path": request.url.path,
        },
    )


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "SmartFlow Traffic Simulation & Optimization Engine",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }


# Static Frontend Hosting (if frontend folder exists)
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    css_dir = os.path.join(frontend_dir, "css")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")

    js_dir = os.path.join(frontend_dir, "js")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "SmartFlow Backend is operational. Visit /docs for developer API."}

