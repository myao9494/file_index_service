"""
アプリケーション設定
- Everything互換のファイルインデックスサービス設定
- ポート8080（Everything HTTP Serverと同じ）
- 環境変数は.envファイルから読み込み
"""
import os
import platform
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# .envファイルを読み込み（存在する場合）
# プロジェクトルートの.envを探す
_env_file = Path(__file__).parent.parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


class Settings(BaseSettings):
    """アプリケーション設定"""

    model_config = SettingsConfigDict(env_prefix="FILE_INDEX_")

    # サーバー設定（Everything互換: デフォルト8080）
    host: str = "0.0.0.0"
    port: int = 8080

    # サービス情報
    version: str = "1.0.0"
    service_name: str = "File Index Service"

    # OS判定
    is_windows: bool = platform.system() == "Windows"

    # 監視対象パス（カンマ区切りで複数指定可能）
    watch_paths: str = ""

    # インデックスDB設定
    index_db_path: str = "data/file_index.db"

    # スキャン設定
    scan_workers: int = 4  # 並列スキャンのワーカー数
    debounce_ms: int = 500  # イベントデバウンス間隔（ミリ秒）
    batch_size: int = 1000  # バッチINSERTサイズ

    # 除外パターン（カンマ区切り）
    ignore_patterns: str = ".git,node_modules,.venv,__pycache__,.DS_Store"

    # デフォルト検索結果数
    default_count: int = 100
    max_count: int = 10000

    @property
    def default_watch_path(self) -> Path:
        """デフォルトの監視パスを取得（環境変数 FILE_INDEX_DEFAULT_PATH で上書き可能）"""
        # 環境変数で指定されている場合はそれを使用
        env_path = os.environ.get("FILE_INDEX_DEFAULT_PATH")
        if env_path:
            return Path(env_path)

        # フォールバック: OSに応じたデフォルト（Documents）
        if self.is_windows:
            user_profile = os.environ.get("USERPROFILE")
            if user_profile:
                return Path(user_profile) / "Documents"
            return Path.home() / "Documents"
        return Path.home() / "Documents"

    @property
    def watch_paths_list(self) -> List[Path]:
        """監視対象パスのリストを取得"""
        paths: List[Path] = []
        if self.watch_paths:
            for p in self.watch_paths.split(","):
                p = p.strip()
                if p:
                    path = Path(p)
                    if path.exists() and path.is_dir():
                        paths.append(path)
        # パスが指定されていない場合はデフォルトを使用
        if not paths:
            default = self.default_watch_path
            if default.exists() and default.is_dir():
                paths.append(default)
        return paths

    @property
    def ignore_patterns_list(self) -> List[str]:
        """除外パターンのリストを取得"""
        return [p.strip() for p in self.ignore_patterns.split(",") if p.strip()]

    @property
    def index_db_full_path(self) -> Path:
        """インデックスDBのフルパスを取得"""
        # backendディレクトリからの相対パス
        backend_dir = Path(__file__).parent.parent
        return backend_dir / self.index_db_path


settings = Settings()
