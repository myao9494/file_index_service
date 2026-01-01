"""
同時実行テスト
データベースロックエラーの再現用
"""
import threading
import tempfile
import time
from pathlib import Path
import pytest
from app.services.index_service import IndexService
import sqlite3
from unittest.mock import patch

class TestConcurrency:
    """同時実行テスト"""
    
    def test_concurrent_writes(self):
        """
        複数のスレッドから同時に書き込みを行い、
        database is locked エラーが発生するか（または修正後はしないか）確認
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_concurrency.db"
            service = IndexService(db_path)
            service.init_db()
            
            # タイムアウトを極端に短くしてエラーを誘発しやすくする
            # 元のconnectをラップしてtimeoutを変更
            original_connect = sqlite3.connect
            def mocked_connect(*args, **kwargs):
                # タイムアウトを0.1秒にする
                kwargs['timeout'] = 0.1
                return original_connect(*args, **kwargs)

            with patch('sqlite3.connect', side_effect=mocked_connect):
                # 同時実行数とループ数
                num_threads = 50
                writes_per_thread = 100
            
                errors = []
            
                def worker(thread_id):
                    # スレッド開始を少しずらすのではなく、一斉に開始するようにバリアなどを使いたいが
                    # 単純にループで負荷をかける
                    for i in range(writes_per_thread):
                        try:
                            service.add_file(
                                path=f"/test/file_{thread_id}_{i}.txt",
                                name=f"file_{thread_id}_{i}.txt",
                                parent_path="/test",
                                file_type="file",
                                extension=".txt",
                                size=100,
                                mtime=time.time(),
                            )
                        except Exception as e:
                            errors.append(e)
                            # エラーが出ても続行して負荷をかけ続ける
                            # break
            
                threads = []
                for i in range(num_threads):
                    t = threading.Thread(target=worker, args=(i,))
                    threads.append(t)
                    t.start()
                
                for t in threads:
                    t.join()
            
            # エラーがあればテスト失敗
            if errors:
                # database is locked エラーが含まれているか確認
                locked_errors = [e for e in errors if "database is locked" in str(e)]
                if locked_errors:
                    pytest.fail(f"Database locked errors occurred: {len(locked_errors)}")
                else:
                    pytest.fail(f"Other errors occurred: {errors[0]}")
            
            # データが正しく書き込まれているか確認
            total_expected = num_threads * writes_per_thread
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM file_metadata")
            count = cursor.fetchone()[0]
            conn.close()
            
            assert count == total_expected, f"Expected {total_expected} files, but got {count}"
