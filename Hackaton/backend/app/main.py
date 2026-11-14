"""Aplicación FastAPI de FuegoClaro."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.errors import FuegoClaroError
from app.core.logging import configure_logging
from app.services.data_store import get_store

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    store = get_store()
    store.refresh(force=True)
    logger.info(
        "FuegoClaro API iniciada | modo=%s | registros=%s | dataset=%s",
        store.mode,
        len(store.df),
        store.manifest.get("dataset_version"),
    )
    yield


app = FastAPI(
    title="FuegoClaro API",
    description=(
        "API de armonización y exploración de focos de calor MODIS y VIIRS (NASA FIRMS) para Ecuador. "
        "Los conteos representan detecciones, no incendios confirmados ni superficie quemada."
    ),
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Data-Mode", "X-Dataset-Version"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.exception_handler(FuegoClaroError)
async def fuegoclaro_error_handler(_: Request, exc: FuegoClaroError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Parámetros inválidos",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        content = detail
    elif isinstance(detail, dict):
        content = {
            "error": {
                "code": detail.get("code", "HTTP_ERROR"),
                "message": detail.get("message", str(detail)),
                "details": detail.get("details", {}),
            }
        }
    else:
        content = {"error": {"code": "HTTP_ERROR", "message": str(detail), "details": {}}}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Error interno del servidor. Revisa los logs del backend.",
                "details": {},
            }
        },
    )


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "app": "FuegoClaro API",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/api/v1/health",
        "meta": "/api/v1/meta",
        "note": "Datos NASA FIRMS. Detección de foco de calor ≠ incendio confirmado ≠ superficie quemada.",
    }
