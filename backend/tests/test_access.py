from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.access import install_access_token


def make_app(token):
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/secret")
    def secret():
        return {"data": 1}

    @app.post("/webhooks/paypal")
    def webhook():
        return {"ok": True}

    enabled = install_access_token(app, token)
    app.add_middleware(CORSMiddleware, allow_origins=["chrome-extension://x"], allow_methods=["*"], allow_headers=["*"])
    return app, enabled


def test_no_token_means_no_check():
    app, enabled = make_app("")
    assert enabled is False
    assert TestClient(app).get("/secret").status_code == 200


def test_requests_without_or_with_wrong_token_are_refused():
    app, enabled = make_app("s3cret")
    assert enabled is True
    c = TestClient(app)
    assert c.get("/secret").status_code == 401
    assert c.get("/secret", headers={"x-access-token": "wrong"}).status_code == 401
    assert c.get("/secret", headers={"x-access-token": "s3cret"}).json() == {"data": 1}


def test_health_and_webhook_stay_open():
    app, _ = make_app("s3cret")
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert c.post("/webhooks/paypal").status_code == 200


def test_preflight_and_cors_headers_on_a_refusal():
    app, _ = make_app("s3cret")
    c = TestClient(app)
    origin = {"origin": "chrome-extension://x"}
    pre = c.options("/secret", headers={**origin, "access-control-request-method": "GET", "access-control-request-headers": "x-access-token"})
    assert pre.status_code == 200
    refused = c.get("/secret", headers=origin)
    assert refused.status_code == 401
    assert refused.headers.get("access-control-allow-origin") == "chrome-extension://x"
