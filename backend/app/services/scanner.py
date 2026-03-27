"""
並列ファイルスキャナー
- ThreadPoolExecutorを使用した並列ディレクトリスキャン
- バッチ処理と進捗コールバック
- 除外パターンによるフィルタリング
"""
import asyncio
import fnmatch
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional


@dataclass
class FileInfo:
    """ファイル情報"""

    path: str
    name: str
    parent_path: str
    file_type: str  # 'file' or 'directory'
    extension: Optional[str]
    size: int
    mtime: float


class ParallelScanner:
    """並列ファイルスキャナー"""

    def __init__(
        self,
        max_workers: int = 4,
        ignore_patterns: Optional[List[str]] = None,
        batch_size: int = 1000,
    ):
        """
        Args:
            max_workers: 並列ワーカー数
            ignore_patterns: 除外パターンリスト（fnmatch形式）
            batch_size: バッチサイズ
        """
        self.max_workers = max_workers
        self.ignore_patterns = ignore_patterns or []
        self.batch_size = batch_size

    def _should_ignore(self, path: Path) -> bool:
        """
        パターンに一致するか確認
        - ファイル名がワイルドカードに一致
        - ファイル名がパターンと完全一致
        - パスにパターンが含まれている（部分一致）
        """
        name = path.name
        path_str = str(path)
        for pattern in self.ignore_patterns:
            if not pattern:
                continue
            # ワイルドカードパターンにマッチするか
            if fnmatch.fnmatch(name, pattern):
                return True
            # ディレクトリ名として完全一致するか
            if name == pattern:
                return True
            # パスにパターンが含まれているか
            if pattern in path_str:
                return True
        return False

    @staticmethod
    def _create_file_info(entry: os.DirEntry) -> Optional[FileInfo]:
        """DirEntryからFileInfoを構築する"""
        try:
            stat = entry.stat(follow_symlinks=False)
            is_dir = entry.is_dir(follow_symlinks=False)
        except (PermissionError, OSError):
            return None

        entry_path = Path(entry.path)
        return FileInfo(
            path=entry.path,
            name=entry.name,
            parent_path=str(entry_path.parent),
            file_type="directory" if is_dir else "file",
            extension=entry_path.suffix if not is_dir else None,
            size=0 if is_dir else stat.st_size,
            mtime=stat.st_mtime,
        )

    def _flush_batch(
        self,
        batch: List[FileInfo],
        on_batch: Optional[Callable[[List[FileInfo]], None]],
    ) -> List[FileInfo]:
        """一定件数以上のバッチをコールバックへ渡す"""
        if on_batch is None:
            return batch

        while len(batch) >= self.batch_size:
            on_batch(batch[: self.batch_size])
            batch = batch[self.batch_size :]

        return batch

    def _scan_directory_sync(self, path: Path) -> List[FileInfo]:
        """ディレクトリを同期的にスキャン（単一ディレクトリのみ）"""
        results: List[FileInfo] = []

        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    item_path = Path(entry.path)
                    if self._should_ignore(item_path):
                        continue

                    file_info = self._create_file_info(entry)
                    if file_info is not None:
                        results.append(file_info)

        except (PermissionError, OSError):
            # ディレクトリ自体へのアクセスエラー
            pass

        return results

    def _scan_recursive_sync(
        self,
        path: Path,
        results: List[FileInfo],
    ) -> None:
        """ディレクトリを再帰的に同期スキャン"""
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    item_path = Path(entry.path)
                    if self._should_ignore(item_path):
                        continue

                    file_info = self._create_file_info(entry)
                    if file_info is None:
                        continue

                    results.append(file_info)

                    if file_info.file_type == "directory":
                        self._scan_recursive_sync(item_path, results)

        except (PermissionError, OSError):
            pass

    async def scan_directory(
        self,
        path: Path,
        on_batch: Optional[Callable[[List[FileInfo]], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> List[FileInfo]:
        """
        ディレクトリを並列スキャン

        Args:
            path: スキャン対象ディレクトリ
            on_batch: バッチコールバック（バッチごとに呼ばれる）
            on_progress: 進捗コールバック（scanned, total）

        Returns:
            FileInfoのリスト
        """
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        loop = asyncio.get_event_loop()
        all_results: List[FileInfo] = []
        scanned_count = 0

        # まず直下のサブディレクトリを列挙
        try:
            subdirs: List[Path] = []
            direct_items: List[FileInfo] = []
            batch: List[FileInfo] = []

            with os.scandir(path) as entries:
                for entry in entries:
                    item_path = Path(entry.path)
                    if self._should_ignore(item_path):
                        continue

                    file_info = self._create_file_info(entry)
                    if file_info is None:
                        continue

                    direct_items.append(file_info)
                    batch.append(file_info)

                    if file_info.file_type == "directory":
                        subdirs.append(item_path)

            all_results.extend(direct_items)
            scanned_count += len(direct_items)

            if on_progress:
                on_progress(scanned_count, -1)  # totalは不明なので-1

            batch = self._flush_batch(batch, on_batch)

        except (PermissionError, OSError):
            return all_results

        # サブディレクトリを並列スキャン
        if subdirs:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:

                def scan_subdir(subdir: Path) -> List[FileInfo]:
                    results: List[FileInfo] = []
                    self._scan_recursive_sync(subdir, results)
                    return results

                # 並列実行
                futures = [
                    loop.run_in_executor(executor, scan_subdir, subdir)
                    for subdir in subdirs
                ]

                # 結果を収集
                for future in asyncio.as_completed(futures):
                    try:
                        subdir_results = await future
                        all_results.extend(subdir_results)
                        scanned_count += len(subdir_results)

                        if on_progress:
                            on_progress(scanned_count, -1)

                        # バッチ処理
                        if on_batch:
                            batch.extend(subdir_results)
                            batch = self._flush_batch(batch, on_batch)

                    except Exception:
                        # エラーは無視して続行
                        continue

                # 残りのバッチを処理
                if on_batch and batch:
                    on_batch(batch)

        return all_results

    async def scan_with_index_service(
        self,
        path: Path,
        index_service,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> int:
        """
        ディレクトリをスキャンしてIndexServiceに登録

        Args:
            path: スキャン対象ディレクトリ
            index_service: IndexServiceインスタンス
            on_progress: 進捗コールバック

        Returns:
            スキャンしたファイル数
        """
        total_count = 0

        def on_batch(batch: List[FileInfo]):
            nonlocal total_count
            files_data = [
                {
                    "path": f.path,
                    "name": f.name,
                    "parent_path": f.parent_path,
                    "file_type": f.file_type,
                    "extension": f.extension,
                    "size": f.size,
                    "mtime": f.mtime,
                }
                for f in batch
            ]
            index_service.batch_add_files(files_data)
            total_count += len(batch)

        await self.scan_directory(path, on_batch=on_batch, on_progress=on_progress)

        return total_count
