"""Acota los cálculos simultáneos sin bloquear las comprobaciones de salud."""

import asyncio


class RequestBudgetMiddleware:
    def __init__(self, app):
        self.app = app
        self._slot = asyncio.Semaphore(1)

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        lightweight = {"/api/v1/health", "/api/v1/meta", "/api/v1/provenance"}
        if scope["type"] != "http" or not path.startswith("/api/v1/") or path in lightweight:
            await self.app(scope, receive, send)
            return
        # Incluye la serialización y el envío: liberar al recibir las cabeceras
        # permitiría mantener varias respuestas grandes simultáneamente.
        async with self._slot:
            await self.app(scope, receive, send)
