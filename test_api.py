# -*- coding: utf-8 -*-
"""
自动化测试套件
-------------
pytest 测试文件，覆盖所有API端点和核心功能。
运行方式：pytest test_api.py -v
"""

import pytest
import httpx
import json
import os
import sys

BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:3000")

# ==================== 测试夹具 ====================

@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, timeout=30.0)

@pytest.fixture
def user_token(client):
    """创建测试用户并返回Token"""
    resp = client.post("/api/register", json={
        "username": f"test_{os.getpid()}",
        "password": "test1234"
    })
    data = resp.json()
    return data.get("access_token", "")

@pytest.fixture
def admin_token(client):
    """获取管理员Token"""
    resp = client.post("/api/admin/login", json={
        "password": "admin_lagrange_2024"
    })
    return resp.json().get("access_token", "")

@pytest.fixture
def auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}

@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ==================== 健康检查测试 ====================

class TestHealthCheck:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_index_status(self, client):
        r = client.get("/api/index-status")
        assert r.status_code == 200
        assert "is_built" in r.json()

    def test_frontend(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert len(r.text) > 1000

    def test_serene(self, client):
        r = client.get("/serene/")
        assert r.status_code == 200


# ==================== 认证测试 ====================

class TestAuth:
    def test_register(self, client):
        r = client.post("/api/register", json={
            "username": "pytest_user",
            "password": "pytest_pass"
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["platform_tokens"] == 10000

    def test_login(self, client, user_token):
        assert user_token is not None
        assert len(user_token) > 20

    def test_user_info(self, client, auth_headers):
        r = client.get("/api/user/me", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "username" in data
        assert "platform_tokens" in data

    def test_unauthorized(self, client):
        r = client.get("/api/user/me")
        assert r.status_code == 401


# ==================== 舰船数据测试 ====================

class TestShipData:
    def test_ship_count(self, client):
        r = client.get("/api/ships")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 20  # 至少20艘

    def test_ship_structure(self, client):
        r = client.get("/api/ships")
        ships = r.json()["ships"]
        for ship in ships[:5]:
            assert "id" in ship
            assert "name" in ship
            assert "type" in ship
            assert "hp" in ship

    def test_ship_types(self, client):
        r = client.get("/api/ships")
        ships = r.json()["ships"]
        types = set(s["type"] for s in ships)
        expected = {"battleship", "battlecruiser", "aircraftcarrier", "cruiser",
                    "destroyer", "frigate", "fighter", "corvette"}
        assert len(types & expected) >= 5  # 至少5种


# ==================== 模拟器存档测试 ====================

class TestSimulatorSave:
    def test_save_fleet(self, client, auth_headers):
        r = client.post("/api/simulator/save", headers=auth_headers, json={
            "save_name": "测试编队",
            "fleet_config": {"ally-escort": {"main": [
                {"id": "test_1", "name": "光追级", "count": 5}
            ]}}
        })
        assert r.status_code == 200
        data = r.json()
        assert data["save_name"] == "测试编队"
        return data["id"]

    def test_list_saves(self, client, auth_headers):
        # 先保存一个
        client.post("/api/simulator/save", headers=auth_headers, json={
            "save_name": "列表测试", "fleet_config": {}
        })
        r = client.get("/api/simulator/saves", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["count"] >= 1

    def test_delete_save(self, client, auth_headers):
        save_id = self.test_save_fleet(client, auth_headers)
        r = client.delete(f"/api/simulator/save/{save_id}", headers=auth_headers)
        assert r.status_code == 200
        assert "删除" in r.json()["message"]


# ==================== 管理员测试 ====================

class TestAdmin:
    def test_admin_login(self, admin_token):
        assert admin_token is not None

    def test_recharge(self, client, admin_headers):
        r = client.post("/api/admin/recharge", headers=admin_headers, json={
            "target_username": "pytest_user",
            "amount": 5000
        })
        assert r.status_code == 200

    def test_logs(self, client, admin_headers):
        r = client.get("/api/admin/logs", headers=admin_headers)
        assert r.status_code == 200

    def test_backup(self, client, admin_headers):
        r = client.post("/api/admin/backup", headers=admin_headers)
        assert r.status_code == 200


# ==================== 性能测试 ====================

class TestPerformance:
    def test_ships_response_time(self, client):
        import time
        start = time.time()
        client.get("/api/ships")
        elapsed = time.time() - start
        assert elapsed < 3.0  # 3秒内响应

    def test_health_response_time(self, client):
        import time
        start = time.time()
        client.get("/health")
        elapsed = time.time() - start
        assert elapsed < 1.0


# ==================== 运行入口 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("  拉格朗日AI — 自动化测试")
    print("=" * 50)
    print(f"  目标服务器: {BASE_URL}")
    print("=" * 50)
    pytest.main([__file__, "-v", "--tb=short"])
