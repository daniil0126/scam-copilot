"""A shared access token for a backend that is reachable from the internet (the judges' hosted copy).

CORS only tells a browser which pages may read an answer; it stops nobody who calls the API directly. The backend holds the
PayPal Sandbox keys and the model key, so on a host it must not answer anonymous callers. With ACCESS_TOKEN set, every call
needs the same value in the `X-Access-Token` header (the release build of the extension sends it). Empty, as in local
development, means no check. The token is in the zip the judges download, so it keeps scanners and strangers out; it is not a
user login (there is one account and the data is Sandbox data).
"""
import hmac
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# `/health` is what the host pings; `/webhooks/paypal` is called by PayPal and is verified by PayPal's own signature.
OPEN_PATHS = {"/health", "/webhooks/paypal"}


def install_access_token(app: FastAPI, token: str | None = None) -> bool:
    """Adds the check to `app`. Call it before adding CORS, so that CORS stays outermost and a 401 still reaches the extension."""
    token = os.getenv("ACCESS_TOKEN", "") if token is None else token
    if not token:
        return False

    @app.middleware("http")
    async def require_access_token(request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in OPEN_PATHS:
            return await call_next(request)
        given = request.headers.get("x-access-token", "")
        if not hmac.compare_digest(given.encode(), token.encode()):
            return JSONResponse({"detail": "Access token missing or wrong."}, status_code=401)
        return await call_next(request)

    return True
