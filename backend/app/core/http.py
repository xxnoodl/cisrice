from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimitMiddleware:
    """Bounds JSON request streams, including requests without Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int = 65536) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > self.max_bytes):
            await JSONResponse({"detail": "Request body too large"}, status_code=413)(
                scope, receive, send
            )
            return
        size = 0

        async def limited() -> Message:
            nonlocal size
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > self.max_bytes:
                    raise HTTPException(413, "Request body too large")
            return message

        await self.app(scope, limited, send)
