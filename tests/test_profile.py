"""Gestaltung je Kind (D176): Grundwerte, Teiländerungen, nur gültige Werte."""
from test_learning import env, child  # noqa: F401
from backend.routers import profile as routes


def test_profile_defaults_partial_updates_and_validation(env):
    client, state, _ = env
    client.app.include_router(routes.router, prefix="/api")
    child(state)
    assert client.get("/api/accounts/1/profile").json() == routes.DEFAULTS
    r = client.put("/api/accounts/1/profile", json={"color": "kobalt", "avatar": "🦊"})
    assert r.status_code == 200 and r.json()["color"] == "kobalt" and r.json()["theme"] == "system"
    assert client.put("/api/accounts/1/profile", json={"theme": "dark"}).json()["avatar"] == "🦊"
    assert client.put("/api/accounts/1/profile", json={"color": "pink"}).status_code == 422
    assert client.get("/api/accounts/2/profile").status_code == 403
