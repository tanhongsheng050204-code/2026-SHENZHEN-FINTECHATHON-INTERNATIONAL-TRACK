"""Every API response carries browser security headers (found missing by an OWASP ZAP API scan)."""

from fastapi.testclient import TestClient

from app.main import app

EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-resource-policy": "same-origin",
}


def test_json_and_error_responses_all_carry_the_headers():
    client = TestClient(app)
    for path in ("/openapi.json", "/auth/me", "/no-such-route"):
        response = client.get(path)
        for name, value in EXPECTED.items():
            assert response.headers.get(name) == value, (path, name)
        policy = response.headers["content-security-policy"]
        assert "default-src 'none'" in policy and "frame-ancestors 'none'" in policy
        assert "unsafe-inline" not in policy
        assert "camera=()" in response.headers["permissions-policy"]


def test_interactive_docs_keep_working_without_the_strict_policy():
    response = TestClient(app).get("/docs")
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
