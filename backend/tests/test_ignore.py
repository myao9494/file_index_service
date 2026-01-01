
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from backend.app.services.index_service import IndexService

class TestIgnoreFeature(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test.db"
        self.service = IndexService(self.db_path)
        self.service.init_db()

    def tearDown(self):
        self.service.close()
        self.test_dir.cleanup()

    def test_add_remove_ignore_patterns(self):
        """除外パターンの追加と削除をテスト"""
        # 初期状態は空
        patterns = self.service.get_ignore_patterns()
        self.assertEqual(patterns, [])

        # 追加
        self.service.add_ignore_pattern("node_modules")
        self.service.add_ignore_pattern("*.pyc")

        patterns = self.service.get_ignore_patterns()
        self.assertEqual(len(patterns), 2)
        self.assertIn("node_modules", patterns)
        self.assertIn("*.pyc", patterns)

        # 重複追加は無視されるべき（エラーにならない）
        self.service.add_ignore_pattern("node_modules")
        patterns = self.service.get_ignore_patterns()
        self.assertEqual(len(patterns), 2)

        # 削除
        self.service.remove_ignore_pattern("node_modules")
        patterns = self.service.get_ignore_patterns()
        self.assertEqual(len(patterns), 1)
        self.assertIn("*.pyc", patterns)

    def test_is_ignored(self):
        """パスが除外対象かどうかの判定をテスト"""
        patterns = ["node_modules", "*.pyc", "__pycache__", ".git"]
        for p in patterns:
            self.service.add_ignore_pattern(p)

        # 除外されるべきケース
        self.assertTrue(self.service.is_ignored("/path/to/node_modules"))
        self.assertTrue(self.service.is_ignored("/path/to/project/node_modules/package.json"))
        self.assertTrue(self.service.is_ignored("/path/to/file.pyc"))
        self.assertTrue(self.service.is_ignored("/path/to/__pycache__/cache.pyc"))
        self.assertTrue(self.service.is_ignored("/path/to/.git/HEAD"))

        # 除外されないケース
        self.assertFalse(self.service.is_ignored("/path/to/main.py"))
        self.assertFalse(self.service.is_ignored("/path/to/project/src/index.ts"))
        
        # 部分一致の確認 (node_modulesが含まれるパス)
        self.assertTrue(self.service.is_ignored("/project/node_modules/lib"))

if __name__ == "__main__":
    unittest.main()
