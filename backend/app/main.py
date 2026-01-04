"""
File Index Service - メインエントリーポイント
Everything互換のファイルインデックス検索サービス

ポート8080でEverythingと同じ形式のAPIを提供
"""
import asyncio
from contextlib import asynccontextmanager
# trigger reload
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.index_service import IndexService
from app.services.scanner import ParallelScanner
from app.services.watcher import FileWatcher
from app.routers import search, admin

# グローバル変数
_index_service: Optional[IndexService] = None
_file_watcher: Optional[FileWatcher] = None


async def start_indexing() -> None:
    """インデックス構築を開始"""
    global _index_service, _file_watcher

    # IndexServiceの初期化
    _index_service = IndexService(settings.index_db_full_path)
    _index_service.init_db()
    _index_service.ensure_trigram_index_populated()
    _index_service.ensure_bigram_index_populated()
    
    # Configの除外パターンをDBに登録
    for pattern in settings.ignore_patterns_list:
        _index_service.add_ignore_pattern(pattern)

    # admin.pyのグローバル変数も更新
    admin._index_service = _index_service

    # 監視パスの登録
    watch_paths = settings.watch_paths_list
    for path in watch_paths:
        _index_service.register_path(str(path))

    # バックグラウンドでスキャン
    paths = _index_service.get_watch_paths()

    for path_info in paths:
        path = path_info["path"]
        status = path_info["status"]

        # idle状態のパスをスキャン
        if status == "idle":
            _index_service.update_path_status(path, "scanning")

            # 既存データを削除して再登録
            _index_service.remove_path(path)
            _index_service.register_path(path)
            _index_service.update_path_status(path, "scanning")
            
            # パターン取得 (DB + Config)
            # 既にDBに入れたのでDBから取得すればOKだが、念のため両方見ておく
            db_patterns = _index_service.get_ignore_patterns()
            patterns = list(set(db_patterns + settings.ignore_patterns_list))

            # スキャン実行
            scanner = ParallelScanner(
                max_workers=settings.scan_workers,
                ignore_patterns=patterns,
                batch_size=settings.batch_size,
            )

            try:
                count = await scanner.scan_with_index_service(
                    Path(path),
                    _index_service,
                )
                _index_service.update_path_stats(path, total_files=count, indexed_files=count)
                _index_service.update_path_status(path, "watching")
            except Exception as e:
                _index_service.update_path_status(path, "error")
                print(f"Error scanning {path}: {e}")

    # インデックス再構築（別スレッドで実行）
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _index_service.rebuild_trigram_index)
    await loop.run_in_executor(None, _index_service.rebuild_bigram_index)

    # ファイル監視を開始
    watch_path_strings = [p["path"] for p in _index_service.get_watch_paths()]
    if watch_path_strings:
        _file_watcher = FileWatcher(
            _index_service,
            debounce_ms=settings.debounce_ms,
            ignore_patterns=settings.ignore_patterns_list,
        )
        _file_watcher.start(watch_path_strings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時
    asyncio.create_task(start_indexing())

    yield

    # 終了時
    global _file_watcher, _index_service
    if _file_watcher is not None:
        _file_watcher.stop()
    if _index_service is not None:
        _index_service.close()


# FastAPIアプリケーション
app = FastAPI(
    title="File Index Service",
    description="Everything互換のファイルインデックス検索サービス",
    version=settings.version,
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(search.router)
app.include_router(admin.router, prefix="", tags=["admin"])

import os
from fastapi.staticfiles import StaticFiles

# 静的ファイルのパス
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

# 静的ファイルが存在する場合のみマウント
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
