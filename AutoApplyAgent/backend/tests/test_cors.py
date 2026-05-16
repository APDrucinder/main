from fastapi.testclient import TestClient

from main import _parse_origins, app


def test_localhost_config_includes_dashboard_port_aliases():
    origins = _parse_origins("http://localhost:3000")

    assert "http://localhost:3001" in origins
    assert "http://127.0.0.1:3000" in origins
    assert "http://127.0.0.1:3001" in origins
    assert "http://localhost:3002" in origins
    assert "http://127.0.0.1:3002" in origins


def test_resume_upload_preflight_allows_dashboard_origin():
    client = TestClient(app)

    response = client.options(
        "/resume/upload",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"
