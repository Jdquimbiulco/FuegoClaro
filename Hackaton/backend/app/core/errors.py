"""Errores de dominio y utilidades de respuesta."""

from fastapi import HTTPException


class FuegoClaroError(Exception):
    """Error base con código estable para el cliente."""

    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class DataNotAvailableError(FuegoClaroError):
    def __init__(self, message: str = "No hay datos cargados. Ejecuta la ingesta o coloca una muestra en data/samples/."):
        super().__init__("DATA_NOT_AVAILABLE", message, status_code=503)


class NotFoundError(FuegoClaroError):
    def __init__(self, message: str = "Recurso no encontrado"):
        super().__init__("NOT_FOUND", message, status_code=404)


def bad_request(message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": message, "details": details or {}})
