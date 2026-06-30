from pathlib import Path

from app.web.pages import APP_ROUTE_URLS, APP_SHELL_URLS, SERVICE_WORKER_CACHE_NAME


def test_service_worker_uses_route_specific_navigation_cache_and_shared_assets(
    client,
):
    response = client.get("/service-worker.js")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["Service-Worker-Allowed"] == "/"
    source = response.text
    assert f'const CACHE_NAME = "{SERVICE_WORKER_CACHE_NAME}";' in source
    assert 'request.mode === "navigate"' in source
    assert "url.pathname" in source
    assert 'networkFirst(request, "/")' not in source
    assert "cache.put(cacheKey, response.clone())" in source
    assert "cache.match(cacheKey)" in source
    assert 'url.pathname === "/service-worker.js"' not in source
    for route in APP_ROUTE_URLS:
        assert f'"{route}"' in source
    for asset_url in APP_SHELL_URLS:
        assert f'"{asset_url}"' in source

    static_source = Path("app/static/service-worker.js").read_text(encoding="utf-8")
    assert "const APP_ROUTE_URLS" not in static_source
    assert "const APP_SHELL_URLS" not in static_source
    assert "const CACHE_NAME" not in static_source


def test_app_shell_urls_are_served(client):
    for asset_url in APP_SHELL_URLS:
        response = client.get(asset_url)
        assert response.status_code == 200, asset_url


def test_manifest_start_url_and_scope_stay_at_root(client):
    response = client.get("/manifest.webmanifest")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
