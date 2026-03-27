"""
性能改善時の回帰防止テスト
- ルート直下の項目もバッチ登録されることを保証する
- 検索のoffset挙動が維持されることを保証する
"""
import tempfile
from pathlib import Path

import pytest

from app.services.index_service import IndexService
from app.services.scanner import ParallelScanner


@pytest.mark.asyncio
async def test_scan_with_index_service_indexes_root_level_entries():
    """ルート直下のファイルとディレクトリもインデックス登録される"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "scan_root"
        root.mkdir()
        (root / "root_file.txt").write_text("root", encoding="utf-8")
        (root / "nested").mkdir()
        (root / "nested" / "child.txt").write_text("child", encoding="utf-8")

        db_path = base / "test.db"
        service = IndexService(db_path)
        service.init_db()

        scanner = ParallelScanner(max_workers=2, batch_size=2)
        indexed_count = await scanner.scan_with_index_service(root, service)

        root_file = service.get_file(str(root / "root_file.txt"))
        nested_dir = service.get_file(str(root / "nested"))
        child_file = service.get_file(str(root / "nested" / "child.txt"))

        service.close()

        assert indexed_count == 3
        assert root_file is not None
        assert nested_dir is not None
        assert child_file is not None


def test_search_offset_returns_stable_slice_without_depth_filter():
    """depth未指定時もoffset付き検索の結果順が維持される"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = IndexService(db_path)
        service.init_db()

        for index in range(6):
            service.add_file(
                path=f"/test/file_{index}.txt",
                name=f"file_{index}.txt",
                parent_path="/test",
                file_type="file",
                extension=".txt",
                size=index,
                mtime=1000 + index,
            )

        results = service.search(
            query="file",
            max_results=2,
            offset=2,
            sort="name",
            ascending=True,
        )

        service.close()

        assert [item["name"] for item in results] == ["file_2.txt", "file_3.txt"]


def test_two_character_search_reflects_newly_added_files():
    """2文字検索でも追加直後のファイルが検索できる"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = IndexService(db_path)
        service.init_db()

        service.add_file(
            path="/test/ab.txt",
            name="ab.txt",
            parent_path="/test",
            file_type="file",
            extension=".txt",
            size=1,
            mtime=1.0,
        )

        results = service.search(query="ab")

        service.close()

        assert [item["name"] for item in results] == ["ab.txt"]
