"""
検索API テスト
Everything互換APIの動作確認
"""
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.index_service import IndexService


@pytest.fixture
def client():
    """テストクライアント"""
    return TestClient(app)


@pytest.fixture
def temp_index_service():
    """一時的なIndexService"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = IndexService(db_path)
        service.init_db()
        yield service
        service.close()


class TestSearchAPI:
    """検索APIテスト"""

    def test_search_empty_query_html(self, client):
        """空のクエリでHTML形式を返す"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_search_empty_query_json(self, client):
        """空のクエリでJSON形式を返す"""
        response = client.get("/?json=1")
        assert response.status_code == 200
        data = response.json()
        assert "totalResults" in data
        assert "results" in data

    def test_search_with_query_json(self, client):
        """クエリ付きでJSON形式を返す"""
        response = client.get("/?search=test&json=1")
        assert response.status_code == 200
        data = response.json()
        assert "totalResults" in data
        assert "results" in data

    def test_search_aliases(self, client):
        """クエリエイリアスが動作する"""
        # s エイリアス
        response = client.get("/?s=test&j=1")
        assert response.status_code == 200

        # q エイリアス
        response = client.get("/?q=test&j=1")
        assert response.status_code == 200

    def test_search_with_count(self, client):
        """結果数指定が動作する"""
        response = client.get("/?json=1&count=10")
        assert response.status_code == 200

    def test_search_with_offset(self, client):
        """オフセット指定が動作する"""
        response = client.get("/?json=1&offset=5")
        assert response.status_code == 200

    def test_search_with_sort(self, client):
        """ソート指定が動作する"""
        response = client.get("/?json=1&sort=name&ascending=1")
        assert response.status_code == 200

        response = client.get("/?json=1&sort=size&ascending=0")
        assert response.status_code == 200

    def test_search_with_file_type(self, client):
        """ファイルタイプフィルタが動作する"""
        response = client.get("/?json=1&file_type=file")
        assert response.status_code == 200

        response = client.get("/?json=1&file_type=directory")
        assert response.status_code == 200


class TestStatusAPI:
    """ステータスAPIテスト"""

    def test_get_status(self, client):
        """ステータスを取得"""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "version" in data
        assert "paths" in data
        assert "total_indexed" in data


class TestPathsAPI:
    """パス管理APIテスト"""

    def test_get_paths(self, client):
        """パス一覧を取得"""
        response = client.get("/paths")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_add_path_not_found(self, client):
        """存在しないパスを追加"""
        response = client.post("/paths", json={"path": "/nonexistent/path"})
        assert response.status_code == 404

    def test_delete_path(self, client):
        """パスを削除"""
        response = client.delete("/paths?path=/some/path")
        assert response.status_code == 200


class TestIndexService:
    """IndexServiceテスト"""

    def test_init_db(self, temp_index_service):
        """データベース初期化"""
        # init_dbはfixtureで呼ばれている
        assert temp_index_service.db_path.exists()

    def test_add_and_get_file(self, temp_index_service):
        """ファイルの追加と取得"""
        temp_index_service.add_file(
            path="/test/file.txt",
            name="file.txt",
            parent_path="/test",
            file_type="file",
            extension=".txt",
            size=100,
            mtime=1234567890.0,
        )

        result = temp_index_service.get_file("/test/file.txt")
        assert result is not None
        assert result["name"] == "file.txt"
        assert result["type"] == "file"

    def test_search(self, temp_index_service):
        """検索"""
        # テストデータ追加
        temp_index_service.add_file(
            path="/test/hello.txt",
            name="hello.txt",
            parent_path="/test",
            file_type="file",
            extension=".txt",
            size=100,
            mtime=1234567890.0,
        )

        results = temp_index_service.search(query="hello")
        assert len(results) >= 1
        assert any(r["name"] == "hello.txt" for r in results)

    def test_register_and_get_watch_paths(self, temp_index_service):
        """監視パスの登録と取得"""
        temp_index_service.register_path("/test/watch")
        paths = temp_index_service.get_watch_paths()
        assert len(paths) >= 1
        assert any(p["path"] == "/test/watch" for p in paths)

    def test_remove_path(self, temp_index_service):
        """パスの削除"""
        temp_index_service.register_path("/test/remove")
        temp_index_service.add_file(
            path="/test/remove/file.txt",
            name="file.txt",
            parent_path="/test/remove",
            file_type="file",
            extension=".txt",
            size=100,
            mtime=1234567890.0,
        )

        temp_index_service.remove_path("/test/remove")

        paths = temp_index_service.get_watch_paths()
        assert not any(p["path"] == "/test/remove" for p in paths)

        result = temp_index_service.get_file("/test/remove/file.txt")
        assert result is None

    def test_get_status(self, temp_index_service):
        """ステータス取得"""
        status = temp_index_service.get_status()
        assert "ready" in status
        assert "paths" in status
        assert "total_files" in status
        assert "indexed_files" in status
