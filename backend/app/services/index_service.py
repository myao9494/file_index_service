"""
ファイルインデックスサービス
- SQLite FTS5を使用した高速ファイル検索
- ファイルメタデータの管理
- 監視パスの管理
"""
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import fnmatch
import threading


class IndexService:
    """ファイルインデックス管理サービス"""

    def __init__(self, db_path: Path):
        """
        Args:
            db_path: SQLiteデータベースファイルのパス
        """
        self.db_path = db_path
        # スレッドごとに異なる接続を持つためのスレッドローカルストレージ
        self._local = threading.local()
        self._trigram_available: Optional[bool] = None  # trigramインデックスの利用可否キャッシュ
        # 書き込み操作を直列化するためのロック
        self._lock = threading.Lock()

    def _get_connection(self) -> sqlite3.Connection:
        """データベース接続を取得（スレッドセーフ）"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path, check_same_thread=False, timeout=30.0
            )  # check_same_thread=Falseは不要だが念のため
            self._local.conn.row_factory = sqlite3.Row
            # WALモードをスレッドごとに有効化（必要であれば）
            self._local.conn.execute("PRAGMA journal_mode = WAL")
        return self._local.conn

    def init_db(self) -> None:
        """データベースを初期化"""
        # ディレクトリが存在しない場合は作成
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # WALモードを有効化（並行読み書き可能）
            cursor.execute("PRAGMA journal_mode = WAL")

        # メタデータテーブル
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS file_metadata (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                parent_path TEXT NOT NULL,
                type TEXT NOT NULL,
                extension TEXT,
                size INTEGER,
                mtime REAL,
                indexed_at REAL
            )
        """
        )

        # パスにインデックスを作成（検索高速化）
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_file_metadata_path
            ON file_metadata(path)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_file_metadata_parent_path
            ON file_metadata(parent_path)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_file_metadata_type
            ON file_metadata(type)
        """
        )

        # ファイル名にインデックスを作成（LIKE検索の高速化）
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_file_metadata_name
            ON file_metadata(name)
        """
        )

        # FTS5仮想テーブル（全文検索用）- レガシー、後方互換性のため残す
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS file_index USING fts5(
                path,
                name,
                parent_path,
                content='file_metadata',
                content_rowid='id'
            )
        """
        )

        # FTS5 trigram仮想テーブル（日本語部分一致対応の高速検索用）
        # trigramトークナイザーは3文字単位でインデックスを作成し、部分一致検索が可能
        try:
            cursor.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS file_name_index USING fts5(
                    name,
                    content='file_metadata',
                    content_rowid='id',
                    tokenize='trigram'
                )
            """
            )
            # trigramインデックス用のトリガー
            cursor.execute(
                """
                CREATE TRIGGER IF NOT EXISTS file_metadata_ai_trigram AFTER INSERT ON file_metadata BEGIN
                    INSERT INTO file_name_index(rowid, name)
                    VALUES (new.id, new.name);
                END
            """
            )
            cursor.execute(
                """
                CREATE TRIGGER IF NOT EXISTS file_metadata_ad_trigram AFTER DELETE ON file_metadata BEGIN
                    INSERT INTO file_name_index(file_name_index, rowid, name)
                    VALUES ('delete', old.id, old.name);
                END
            """
            )
            cursor.execute(
                """
                CREATE TRIGGER IF NOT EXISTS file_metadata_au_trigram AFTER UPDATE ON file_metadata BEGIN
                    INSERT INTO file_name_index(file_name_index, rowid, name)
                    VALUES ('delete', old.id, old.name);
                    INSERT INTO file_name_index(rowid, name)
                    VALUES (new.id, new.name);
                END
            """
            )
        except sqlite3.OperationalError:
            # trigramトークナイザーが利用できない場合（SQLite < 3.34）はスキップ
            pass

        # bigramテーブル（2文字検索高速化用）
        # ファイル名から全ての2文字ペアを抽出して格納
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS file_name_bigrams (
                file_id INTEGER NOT NULL,
                bigram TEXT NOT NULL,
                FOREIGN KEY (file_id) REFERENCES file_metadata(id) ON DELETE CASCADE
            )
        """
        )

        # bigramにインデックスを作成（高速ルックアップ用）
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_file_name_bigrams_bigram
            ON file_name_bigrams(bigram)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_file_name_bigrams_file_id
            ON file_name_bigrams(file_id)
        """
        )

        # FTS5トリガー（メタデータテーブルと同期）
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS file_metadata_ai AFTER INSERT ON file_metadata BEGIN
                INSERT INTO file_index(rowid, path, name, parent_path)
                VALUES (new.id, new.path, new.name, new.parent_path);
            END
        """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS file_metadata_ad AFTER DELETE ON file_metadata BEGIN
                INSERT INTO file_index(file_index, rowid, path, name, parent_path)
                VALUES ('delete', old.id, old.path, old.name, old.parent_path);
            END
        """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS file_metadata_au AFTER UPDATE ON file_metadata BEGIN
                INSERT INTO file_index(file_index, rowid, path, name, parent_path)
                VALUES ('delete', old.id, old.path, old.name, old.parent_path);
                INSERT INTO file_index(rowid, path, name, parent_path)
                VALUES (new.id, new.path, new.name, new.parent_path);
            END
        """
        )

        # 監視パステーブル
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_paths (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                enabled INTEGER DEFAULT 1,
                total_files INTEGER DEFAULT 0,
                indexed_files INTEGER DEFAULT 0,
                status TEXT DEFAULT 'idle',
                last_full_scan REAL,
                last_updated REAL,
                error_message TEXT
            )
        """
        )

        # 無視パターンのテーブル
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ignore_patterns (
                id INTEGER PRIMARY KEY,
                pattern TEXT UNIQUE NOT NULL
            )
        """
        )

        conn.commit()

    def add_file(
        self,
        path: str,
        name: str,
        parent_path: str,
        file_type: str,
        extension: Optional[str],
        size: int,
        mtime: float,
    ) -> None:
        """ファイルをインデックスに追加"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO file_metadata
                (path, name, parent_path, type, extension, size, mtime, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (path, name, parent_path, file_type, extension, size, mtime, time.time()),
            )
            conn.commit()

    def get_file(self, path: str) -> Optional[Dict[str, Any]]:
        """パスでファイル情報を取得"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM file_metadata WHERE path = ?", (path,))
        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    def update_file(self, path: str, **kwargs) -> None:
        """ファイル情報を更新"""
        if not kwargs:
            return

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 更新するカラムと値を構築
            set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
            values = list(kwargs.values()) + [path]

            cursor.execute(
                f"UPDATE file_metadata SET {set_clause} WHERE path = ?",
                values,
            )
            conn.commit()

    def remove_file(self, path: str) -> None:
        """ファイルをインデックスから削除"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM file_metadata WHERE path = ?", (path,))
            conn.commit()

    def batch_add_files(self, files: List[Dict[str, Any]]) -> None:
        """バッチでファイルを追加"""
        if not files:
            return

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            indexed_at = time.time()

            cursor.executemany(
                """
                INSERT OR REPLACE INTO file_metadata
                (path, name, parent_path, type, extension, size, mtime, indexed_at)
                VALUES (:path, :name, :parent_path, :file_type, :extension, :size, :mtime, :indexed_at)
            """,
                [{**f, "indexed_at": indexed_at} for f in files],
            )
            conn.commit()

    def get_file_count(self) -> int:
        """インデックス内のファイル数を取得"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM file_metadata")
        return cursor.fetchone()[0]

    @staticmethod
    def _extract_bigrams(name: str) -> List[str]:
        """ファイル名から全ての2文字ペア（bigram）を抽出"""
        if len(name) < 2:
            return []
        return [name[i : i + 2] for i in range(len(name) - 1)]

    def _add_bigrams_for_file(self, file_id: int, name: str) -> None:
        """ファイルのbigramをインデックスに追加"""
        bigrams = self._extract_bigrams(name)
        if not bigrams:
            return

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 重複を除去してバッチ挿入
            unique_bigrams = list(set(bigrams))
            cursor.executemany(
                "INSERT INTO file_name_bigrams (file_id, bigram) VALUES (?, ?)",
                [(file_id, bg) for bg in unique_bigrams],
            )

    def _remove_bigrams_for_file(self, file_id: int) -> None:
        """ファイルのbigramをインデックスから削除"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_name_bigrams WHERE file_id = ?", (file_id,))

    def rebuild_bigram_index(self) -> None:
        """bigramインデックスを既存データから再構築"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 既存のbigramインデックスをクリア
            cursor.execute("DELETE FROM file_name_bigrams")

            # 全ファイルからbigramを抽出して挿入
            cursor.execute("SELECT id, name FROM file_metadata")
            rows = cursor.fetchall()

            bigram_data = []
            for row in rows:
                file_id = row[0]
                name = row[1]
                bigrams = self._extract_bigrams(name)
                unique_bigrams = list(set(bigrams))
                bigram_data.extend([(file_id, bg) for bg in unique_bigrams])

            # バッチ挿入
            if bigram_data:
                cursor.executemany(
                    "INSERT INTO file_name_bigrams (file_id, bigram) VALUES (?, ?)",
                    bigram_data,
                )

            conn.commit()

    def ensure_bigram_index_populated(self) -> None:
        """bigramインデックスが空の場合、既存データから構築"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) FROM file_name_bigrams")
            bigram_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM file_metadata")
            metadata_count = cursor.fetchone()[0]

            # メタデータがあるのにbigramが空なら再構築
            if metadata_count > 0 and bigram_count == 0:
                self.rebuild_bigram_index()
        except sqlite3.OperationalError:
            pass  # テーブルが存在しない場合は無視

    def _has_trigram_index(self) -> bool:
        """trigramインデックスが利用可能かチェック（キャッシュ付き）"""
        if self._trigram_available is not None:
            return self._trigram_available

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='file_name_index'"
            )
            self._trigram_available = cursor.fetchone() is not None
        except sqlite3.OperationalError:
            self._trigram_available = False
        return self._trigram_available

    def rebuild_trigram_index(self) -> None:
        """trigramインデックスを既存データから再構築"""
        if not self._has_trigram_index():
            return

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 既存のtrigramインデックスをクリア
            try:
                cursor.execute("DELETE FROM file_name_index")
            except sqlite3.OperationalError:
                return  # trigramテーブルが存在しない場合

            # 全データを再インデックス
            cursor.execute(
                """
                INSERT INTO file_name_index(rowid, name)
                SELECT id, name FROM file_metadata
            """
            )
            conn.commit()

    def ensure_trigram_index_populated(self) -> None:
        """trigramインデックスが空の場合、既存データから構築"""
        if not self._has_trigram_index():
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        # trigramインデックスのエントリ数を確認
        try:
            cursor.execute("SELECT COUNT(*) FROM file_name_index")
            trigram_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM file_metadata")
            metadata_count = cursor.fetchone()[0]

            # メタデータがあるのにtrigramが空なら再構築
            if metadata_count > 0 and trigram_count == 0:
                self.rebuild_trigram_index()
        except sqlite3.OperationalError:
            pass  # テーブルが存在しない場合は無視

    def search(
        self,
        query: str = "",
        path_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        max_results: int = 1000,
        depth: int = 0,
        offset: int = 0,
        sort: str = "name",
        ascending: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        ファイルを検索

        検索戦略:
        - 3文字以上: FTS5 trigramインデックス（高速）
        - 2文字: bigramインデックス（高速）
        - 1文字: LIKE検索（フォールバック）
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 使用するインデックスタイプを追跡（パスフィルタ時のテーブルエイリアス判定用）
        using_indexed_search = False

        if query:
            query_len = len(query)

            if self._has_trigram_index() and query_len >= 3:
                # 3文字以上: FTS5 trigram検索（高速）
                sql = """
                    SELECT m.*
                    FROM file_metadata m
                    JOIN file_name_index fi ON m.id = fi.rowid
                    WHERE file_name_index MATCH ?
                """
                params: List[Any] = [f'"{query}"']
                using_indexed_search = True
            elif query_len == 2:
                # 2文字: bigramインデックス検索（高速）
                sql = """
                    SELECT DISTINCT m.*
                    FROM file_metadata m
                    JOIN file_name_bigrams b ON m.id = b.file_id
                    WHERE b.bigram = ?
                """
                params = [query]
                using_indexed_search = True
            else:
                # 1文字: LIKE検索（フォールバック）
                sql = """
                    SELECT * FROM file_metadata
                    WHERE name LIKE ?
                """
                params = [f"%{query}%"]
        else:
            # 空クエリの場合は全件取得
            sql = "SELECT * FROM file_metadata WHERE 1=1"
            params = []

        # パスフィルタ
        if path_filter:
            if using_indexed_search:
                sql += " AND m.path LIKE ?"
            else:
                sql += " AND path LIKE ?"
            params.append(f"{path_filter}%")

        # タイプフィルタ
        if type_filter and type_filter != "all":
            if using_indexed_search:
                sql += " AND m.type = ?"
            else:
                sql += " AND type = ?"
            params.append(type_filter)

        # ソート
        sort_column = sort if sort in ["name", "path", "size", "mtime"] else "name"
        sort_direction = "ASC" if ascending else "DESC"
        if using_indexed_search:
            sql += f" ORDER BY m.{sort_column} {sort_direction}"
        else:
            sql += f" ORDER BY {sort_column} {sort_direction}"

        # 結果数制限
        # depthフィルタがある場合はSQLでLIMITをかけず（多めに取得）、後でフィルタリングする
        limit_count = max_results + offset
        if depth > 0 and path_filter:
            limit_count = 100000  # 十分に大きな値

        sql += " LIMIT ?"
        params.append(limit_count)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # 階層フィルタリングと結果整形
        results = []
        base_path_obj = Path(path_filter) if path_filter and depth > 0 else None
        skipped = 0

        for row in rows:
            if len(results) >= max_results:
                break

            result_dict = dict(row)

            # depthフィルタリング
            if base_path_obj:
                try:
                    p = Path(result_dict["path"])
                    rel_path = p.relative_to(base_path_obj)

                    # 階層深度（partsの数）がdepthを超えたらスキップ
                    if len(rel_path.parts) > depth:
                        continue
                except (ValueError, RuntimeError):
                    continue

            # オフセット処理
            if skipped < offset:
                skipped += 1
                continue

            results.append(result_dict)

        return results

    def register_path(self, path: str) -> None:
        """監視パスを登録"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO watch_paths (path, last_updated)
                VALUES (?, ?)
            """,
                (path, time.time()),
            )
            conn.commit()

    def get_watch_paths(self) -> List[Dict[str, Any]]:
        """監視パス一覧を取得"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM watch_paths ORDER BY path")
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def update_path_status(self, path: str, status: str) -> None:
        """監視パスのステータスを更新"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE watch_paths
                SET status = ?, last_updated = ?
                WHERE path = ?
            """,
                (status, time.time(), path),
            )
            conn.commit()

    def update_path_stats(
        self,
        path: str,
        total_files: Optional[int] = None,
        indexed_files: Optional[int] = None,
    ) -> None:
        """監視パスの統計情報を更新"""
        updates = []
        params: List[Any] = []

        if total_files is not None:
            updates.append("total_files = ?")
            params.append(total_files)

        if indexed_files is not None:
            updates.append("indexed_files = ?")
            params.append(indexed_files)

        if not updates:
            return

        updates.append("last_updated = ?")
        params.append(time.time())
        params.append(path)

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                f"UPDATE watch_paths SET {', '.join(updates)} WHERE path = ?",
                params,
            )
            conn.commit()

    def remove_path(self, path: str) -> None:
        """監視パスを削除（関連ファイルも削除）"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 関連ファイルを削除（パスで始まるもの）
            cursor.execute(
                "DELETE FROM file_metadata WHERE path LIKE ? OR parent_path LIKE ?",
                (f"{path}%", f"{path}%"),
            )

            # 監視パスを削除
            cursor.execute("DELETE FROM watch_paths WHERE path = ?", (path,))

            conn.commit()

    def get_status(self) -> Dict[str, Any]:
        """インデックス状態を取得"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 監視パス一覧
        paths = self.get_watch_paths()

        # 統計の集計
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(total_files), 0) as total_files,
                COALESCE(SUM(indexed_files), 0) as indexed_files
            FROM watch_paths
        """
        )
        row = cursor.fetchone()

        # ready判定: scanning中のパスがなく、少なくとも1つのパスがwatching状態
        is_ready = (
            len(paths) > 0
            and not any(p["status"] == "scanning" for p in paths)
            and any(p["status"] == "watching" for p in paths)
        )

        return {
            "ready": is_ready,
            "paths": paths,
            "total_files": row["total_files"],
            "indexed_files": row["indexed_files"],
        }

    def is_path_indexed(self, path: str) -> bool:
        """
        パスがインデックスされているか確認

        パス自体または親パスが watch_paths に登録されていればTrue

        Args:
            path: チェックするパス

        Returns:
            インデックスされていればTrue
        """
        return self.get_covering_watch_path(path) is not None

    def get_covering_watch_path(self, path: str) -> Optional[str]:
        """
        パスをカバーする監視パスを取得

        Args:
            path: チェックするパス

        Returns:
            カバーする監視パス（存在しなければNone）
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 登録されている全監視パスを取得
        cursor.execute("SELECT path FROM watch_paths WHERE enabled = 1 ORDER BY length(path) DESC")
        rows = cursor.fetchall()

        # 正規化
        check_path = Path(path).resolve()
        check_path_str = str(check_path)

        for row in rows:
            watch_path = Path(row["path"]).resolve()
            watch_path_str = str(watch_path)

            # 完全一致またはサブパスか確認
            if check_path_str == watch_path_str:
                return row["path"]

            # check_path が watch_path のサブパスか
            try:
                check_path.relative_to(watch_path)
                return row["path"]
            except ValueError:
                continue

        return None

    async def register_path_async(self, path: str) -> None:
        """
        非同期でパスを登録

        Args:
            path: 登録するパス
        """
        # 同期メソッドを呼び出し（SQLiteは同期的）
        self.register_path(path)

    def close(self) -> None:
        """データベース接続を閉じる（現在のスレッド用）"""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def add_ignore_pattern(self, pattern: str) -> None:
        """無視パターンを追加"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO ignore_patterns (pattern) VALUES (?)", (pattern,)
            )
            conn.commit()

    def remove_ignore_pattern(self, pattern: str) -> None:
        """無視パターンを削除"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ignore_patterns WHERE pattern = ?", (pattern,))
            conn.commit()

    def get_ignore_patterns(self) -> List[str]:
        """無視パターン一覧を取得"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT pattern FROM ignore_patterns ORDER BY pattern")
        return [row[0] for row in cursor.fetchall()]

    def is_ignored(self, path: str) -> bool:
        """
        パスが無視対象かチェックする
        
        Args:
            path: チェックするパス (絶対パスであることが好ましい)
            
        Returns:
            無視対象であれば True
        """
        patterns = self.get_ignore_patterns()
        if not patterns:
            return False

        path_obj = Path(path)
        path_str = str(path_obj)
        parts = path_obj.parts

        for pattern in patterns:
            # 1. 単純なglobマッチング (フルパスに対して)
            if fnmatch.fnmatch(path_str, pattern):
                return True
            
            # 2. ファイル名/ディレクトリ名単体でのマッチング (例: node_modules, .git)
            # パスの一部にパターンにマッチするものがあれば除外とする
            # ただし、パターンがセパレータを含まない場合のみ有効 (例: "src/foo" は部分一致させない)
            if "/" not in pattern and "\\" not in pattern:
                for part in parts:
                    if fnmatch.fnmatch(part, pattern):
                        return True
                        
        return False
