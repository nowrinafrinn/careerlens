"""Rejects oversized uploads before their body is read.

FastAPI parses multipart bodies (spooling files to disk) before the route
runs, so a size check inside the route would come too late to stop a huge
upload. This checks the declared Content-Length first. The route still
checks the real size, in case the header is missing or wrong.
"""

from starlette.types import ASGIApp, Receive, Scope, Send

from app.errors import error_response

# Room for multipart boundaries and the other form fields.
MULTIPART_OVERHEAD = 64 * 1024


class UploadSizeLimit:
    def __init__(self, app: ASGIApp, path_prefix: str, max_bytes: int) -> None:
        self.app = app
        self.path_prefix = path_prefix
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"].startswith(self.path_prefix):
            length = dict(scope["headers"]).get(b"content-length")
            if length is not None and length.isdigit() and int(length) > self.max_bytes + MULTIPART_OVERHEAD:
                megabytes = self.max_bytes // (1024 * 1024)
                response = error_response(413, "file_too_large", f"The file is larger than the {megabytes} MB limit.")
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
