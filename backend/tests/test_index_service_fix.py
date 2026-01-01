"""
統計情報更新エラーの再現テスト
"""
import tempfile
from pathlib import Path
import pytest
from app.services.index_service import IndexService
import sqlite3

class TestIndexServiceFix:
    """IndexService修正テスト"""
    
    def test_update_path_stats_binding_error(self):
        """update_path_statsでのバインディングエラーを再現"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_fix.db"
            service = IndexService(db_path)
            service.init_db()
            
            # 手動でパスを登録しないと更新できない
            service.register_path("/test/path")
            
            # エラーが発生するか確認
            try:
                service.update_path_stats(
                    path="/test/path",
                    total_files=10,
                    indexed_files=5
                )
            except sqlite3.ProgrammingError as e:
                # Incorrect number of bindings supplied...
                assert "Incorrect number of bindings supplied" in str(e)
                pytest.fail(f"Binding error occurred: {e}")
            except Exception as e:
                 # その他のエラーも含めて失敗とみなす
                 pytest.fail(f"An unexpected error occurred: {e}")
