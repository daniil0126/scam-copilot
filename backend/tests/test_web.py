import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.access import install_access_token
from app.web import install_web


def make(tmp_path, token="tok"):
    (tmp_path / "index.html").write_text("<html>panel</html>")
    (tmp_path / "x.js").write_text("console.log(1)")
    app = FastAPI()

    @app.get("/checks")
    def checks():
        return []

    install_access_token(app, token)
    assert install_web(app, tmp_path, token=token) is True
    return TestClient(app)


def test_not_installed_without_a_build(tmp_path):
    assert install_web(FastAPI(), tmp_path) is False


def test_the_page_and_its_files_load_without_a_token(tmp_path):
    c = make(tmp_path)
    assert c.get("/app/").status_code == 200 and "panel" in c.get("/app/").text
    assert c.get("/app/x.js").status_code == 200
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/app/"


def test_config_js_hands_the_page_its_token(tmp_path):
    r = make(tmp_path, token="abc'\"123").get("/app/config.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-store"
    value = r.text.split("=", 1)[1].strip().rstrip(";")
    assert json.loads(value) == {"token": "abc'\"123"}  # escaped, not pasted into the script


def test_the_api_still_needs_the_token(tmp_path):
    c = make(tmp_path)
    assert c.get("/checks").status_code == 401
    assert c.get("/checks", headers={"x-access-token": "tok"}).status_code == 200
