"""
ファイルシステム監視サービス
- watchdogを使用したファイル変更検知
- デバウンス処理による連続イベントの集約
- IndexServiceとの連携
"""
import asyncio
import fnmatch
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from app.services.index_service import IndexService


class IndexEventHandler(FileSystemEventHandler):
    """ファイルシステムイベントをインデックスに反映するハンドラー"""

    def __init__(
        self,
        index_service: IndexService,
        debounce_ms: int = 500,
        ignore_patterns: Optional[List[str]] = None,
    ):
        """
        Args:
            index_service: インデックスサービス
            debounce_ms: デバウンス間隔（ミリ秒）
            ignore_patterns: 除外パターンリスト
        """
        super().__init__()
        self.index_service = index_service
        self.debounce_ms = debounce_ms
        self.ignore_patterns = ignore_patterns or []

        # イベントキュー: {path: (event_type, is_directory, timestamp)}
        self._pending_events: Dict[str, Tuple[str, bool, float]] = {}
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # 非同期処理用
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()

    def _should_ignore(self, path: str) -> bool:
        """パスが除外パターンに一致するか確認"""
        # IndexServiceに委譲（DB設定 + config設定）
        # ただし、config設定はmain.pyでDBに登録される前提
        return self.index_service.is_ignored(path)

    def _queue_event(
        self, event_type: str, path: str, is_directory: bool = False
    ) -> None:
        """イベントをキューに追加（デバウンス）"""
        if self._should_ignore(path):
            return

        with self._lock:
            # 既存のイベントを上書き（最新のイベントのみ保持）
            self._pending_events[path] = (event_type, is_directory, time.time())

            # タイマーをリセット
            if self._timer is not None:
                self._timer.cancel()

            # デバウンス後に処理を実行
            self._timer = threading.Timer(
                self.debounce_ms / 1000.0, self._process_pending_events
            )
            self._timer.start()

    def _process_pending_events(self) -> None:
        """保留中のイベントを処理"""
        with self._lock:
            events = self._pending_events.copy()
            self._pending_events.clear()

        for path, (event_type, is_directory, _) in events.items():
            self._apply_event(event_type, path, is_directory)

    def _apply_event(self, event_type: str, path: str, is_directory: bool) -> None:
        """イベントをインデックスに適用"""
        path_obj = Path(path)

        if event_type == "deleted":
            # 削除イベント
            self.index_service.remove_file(path)

        elif event_type in ("created", "modified"):
            # 作成または更新イベント
            if not path_obj.exists():
                # ファイルが存在しない場合はスキップ
                return

            try:
                stat = path_obj.stat()

                self.index_service.add_file(
                    path=path,
                    name=path_obj.name,
                    parent_path=str(path_obj.parent),
                    file_type="directory" if is_directory else "file",
                    extension=path_obj.suffix if not is_directory else None,
                    size=0 if is_directory else stat.st_size,
                    mtime=stat.st_mtime,
                )
            except (PermissionError, OSError):
                # エラーは無視
                pass

        elif event_type == "moved":
            # 移動イベント（削除 + 作成として処理）
            # 移動元は削除済みなのでスキップ
            pass

    async def flush(self) -> None:
        """保留中のイベントを即座に処理"""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        self._process_pending_events()

    # watchdogイベントハンドラー

    def on_created(self, event: FileSystemEvent) -> None:
        """ファイル/ディレクトリ作成イベント"""
        self._queue_event("created", event.src_path, event.is_directory)

    def on_deleted(self, event: FileSystemEvent) -> None:
        """ファイル/ディレクトリ削除イベント"""
        self._queue_event("deleted", event.src_path, event.is_directory)

    def on_modified(self, event: FileSystemEvent) -> None:
        """ファイル更新イベント"""
        # ディレクトリの更新は無視（中身の変更は個別イベントで通知される）
        if not event.is_directory:
            self._queue_event("modified", event.src_path, event.is_directory)

    def on_moved(self, event: FileSystemEvent) -> None:
        """ファイル/ディレクトリ移動イベント"""
        # 移動元を削除
        self._queue_event("deleted", event.src_path, event.is_directory)
        # 移動先を作成
        if hasattr(event, "dest_path"):
            self._queue_event("created", event.dest_path, event.is_directory)


class FileWatcher:
    """ファイルシステム監視サービス"""

    def __init__(
        self,
        index_service: IndexService,
        debounce_ms: int = 500,
        ignore_patterns: Optional[List[str]] = None,
    ):
        """
        Args:
            index_service: インデックスサービス
            debounce_ms: デバウンス間隔（ミリ秒）
            ignore_patterns: 除外パターンリスト
        """
        self.index_service = index_service
        self.debounce_ms = debounce_ms
        self.ignore_patterns = ignore_patterns or []

        self._observer: Optional[Observer] = None
        self._handler: Optional[IndexEventHandler] = None
        self._running = False

    def start(self, paths: List[str]) -> None:
        """
        ファイル監視を開始

        Args:
            paths: 監視対象パスのリスト
        """
        if self._running:
            self.stop()

        self._handler = IndexEventHandler(
            self.index_service,
            debounce_ms=self.debounce_ms,
            ignore_patterns=self.ignore_patterns,
        )

        self._observer = Observer()

        for path in paths:
            path_obj = Path(path)
            if path_obj.exists() and path_obj.is_dir():
                self._observer.schedule(self._handler, path, recursive=True)

        self._observer.start()
        self._running = True

    def stop(self) -> None:
        """ファイル監視を停止"""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        self._handler = None
        self._running = False

    def is_running(self) -> bool:
        """監視中かどうか"""
        return self._running

    def add_path(self, path: str) -> None:
        """監視パスを追加"""
        if self._observer is not None and self._handler is not None:
            path_obj = Path(path)
            if path_obj.exists() and path_obj.is_dir():
                self._observer.schedule(self._handler, path, recursive=True)

    async def flush(self) -> None:
        """保留中のイベントを即座に処理"""
        if self._handler is not None:
            await self._handler.flush()
