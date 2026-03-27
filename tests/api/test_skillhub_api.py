"""SkillHub API 路由测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def client():
    """使用 FastAPI 的 dependency_overrides 注入 mock"""
    from main import app
    from fastapi.testclient import TestClient

    mock_hub = MagicMock()
    mock_hub.fetch_index = AsyncMock(return_value=MagicMock(
        model_dump=lambda: {"version": 1, "updated_at": "", "plugins": []}
    ))
    mock_hub.search = AsyncMock(return_value=[])
    mock_hub.list_installed = MagicMock(return_value=[])
    mock_hub.install = AsyncMock(return_value={"status": "installed", "version": "1.0.0"})
    mock_hub.uninstall = AsyncMock(return_value={"status": "uninstalled", "name": "test"})

    # 使用 FastAPI 的 DI override
    from api.skillhub import get_skillhub_manager
    app.dependency_overrides[get_skillhub_manager] = lambda: mock_hub

    # mock registry for installed endpoint
    with patch("api.skillhub._get_registry") as mock_reg:
        mock_reg.return_value.list_plugins.return_value = []
        yield TestClient(app), mock_hub

    app.dependency_overrides.clear()


class TestSkillHubAPI:

    def test_get_registry(self, client):
        c, _ = client
        resp = c.get("/api/skillhub/registry")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_get_installed(self, client):
        c, _ = client
        resp = c.get("/api/skillhub/installed")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_search(self, client):
        c, _ = client
        resp = c.get("/api/skillhub/search?q=健身")
        assert resp.status_code == 200

    def test_install(self, client):
        c, _ = client
        resp = c.post("/api/skillhub/install", json={"name": "fitness_agent"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "installed"

    def test_uninstall(self, client):
        c, _ = client
        resp = c.delete("/api/skillhub/uninstall/fitness_agent")
        assert resp.status_code == 200

    def test_install_error(self, client):
        c, mock_hub = client
        mock_hub.install = AsyncMock(side_effect=ValueError("not found"))
        resp = c.post("/api/skillhub/install", json={"name": "bad"})
        assert resp.status_code == 400
