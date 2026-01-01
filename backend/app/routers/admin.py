"""
管理API
- インデックス状態の取得
- 監視パスの管理
- インデックスの再構築
"""
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from app.config import settings
from app.services.index_service import IndexService
from app.services.scanner import ParallelScanner

router = APIRouter()

# グローバルなIndexServiceインスタンス
_index_service: Optional[IndexService] = None


def get_index_service() -> IndexService:
    """IndexServiceインスタンスを取得"""
    # ensure changes are picked up
    global _index_service
    if _index_service is None:
        _index_service = IndexService(settings.index_db_full_path)
        _index_service.init_db()
    return _index_service


class PathRequest(BaseModel):
    """パスリクエスト"""

    path: str


class IgnorePatternRequest(BaseModel):
    """無視パターンリクエスト"""

    pattern: str


@router.get("/status")
async def get_status():
    """
    インデックス状態を取得

    Returns:
        ready: 準備完了かどうか
        version: サービスバージョン
        paths: 監視パス一覧
        total_indexed: 総インデックス数
    """
    index_service = get_index_service()
    status = index_service.get_status()

    return {
        "ready": status["ready"],
        "version": settings.version,
        "paths": [
            {
                "path": p["path"],
                "status": p["status"],
                "indexed_files": p["indexed_files"],
                "total_files": p["total_files"],
                "error_message": p.get("error_message"),
            }
            for p in status["paths"]
        ],
        "total_indexed": status["indexed_files"],
    }


@router.get("/paths")
async def get_paths():
    """
    監視パス一覧を取得

    Returns:
        監視パスのリスト
    """
    index_service = get_index_service()
    paths = index_service.get_watch_paths()

    return [
        {
            "id": p["id"],
            "path": p["path"],
            "enabled": p["enabled"],
            "status": p["status"],
            "total_files": p["total_files"],
            "indexed_files": p["indexed_files"],
            "last_full_scan": p.get("last_full_scan"),
            "last_updated": p.get("last_updated"),
            "error_message": p.get("error_message"),
        }
        for p in paths
    ]


@router.post("/paths")
async def add_path(request: PathRequest, background_tasks: BackgroundTasks):
    """
    監視パスを追加してスキャンを開始

    Args:
        request: パスリクエスト

    Returns:
        追加結果
    """
    path = request.path
    path_obj = Path(path)

    # パスの存在確認
    if not path_obj.exists():
        raise HTTPException(status_code=404, detail=f"パスが見つかりません: {path}")

    if not path_obj.is_dir():
        raise HTTPException(status_code=400, detail=f"ディレクトリではありません: {path}")

    index_service = get_index_service()

    # すでにインデックス済みか確認
    if index_service.is_path_indexed(path):
        return {"path": path, "status": "already_indexed"}

    # パスを登録
    index_service.register_path(path)
    index_service.update_path_status(path, "scanning")

    # バックグラウンドでスキャン開始
    background_tasks.add_task(_scan_path, path)

    return {"path": path, "status": "scanning"}


@router.delete("/paths")
async def remove_path(path: str = Query(..., description="削除するパス")):
    """
    監視パスを削除

    Args:
        path: 削除するパス

    Returns:
        削除結果
    """
    index_service = get_index_service()
    index_service.remove_path(path)

    return {"path": path, "status": "removed"}


@router.get("/ignores")
async def get_ignores():
    """
    無視パターン一覧を取得

    Returns:
        無視パターンのリスト
    """
    index_service = get_index_service()
    return index_service.get_ignore_patterns()


@router.post("/ignores")
async def add_ignore(request: IgnorePatternRequest):
    """
    無視パターンを追加

    Args:
        request: パターンリクエスト

    Returns:
        追加結果
    """
    index_service = get_index_service()
    index_service.add_ignore_pattern(request.pattern)
    return {"pattern": request.pattern, "status": "added"}


@router.delete("/ignores")
async def remove_ignore(pattern: str = Query(..., description="削除するパターン")):
    """
    無視パターンを削除

    Args:
        pattern: 削除するパターン

    Returns:
        削除結果
    """
    index_service = get_index_service()
    index_service.remove_ignore_pattern(pattern)
    return {"pattern": pattern, "status": "removed"}


@router.post("/ignores/defaults")
async def add_default_ignores():
    """
    Python開発の一般的な無視パターンを追加

    Returns:
        追加結果
    """
    defaults = [
        "__pycache__",
        "*.pyc",
        ".git",
        ".venv",
        ".DS_Store",
        "node_modules",
        "venv",
        "env",
        ".idea",
        ".vscode",
    ]
    index_service = get_index_service()
    for pattern in defaults:
        index_service.add_ignore_pattern(pattern)
    
    return {"status": "added", "patterns": defaults}


@router.post("/rebuild")
async def rebuild_index(
    background_tasks: BackgroundTasks,
    path: Optional[str] = Query(None, description="再構築対象パス（空の場合は全パス）"),
    ignore_patterns: Optional[str] = Query(None, description="除外パターン（カンマ区切り）"),
):
    """
    インデックスを再構築

    Args:
        path: 再構築対象パス（空の場合は全パス）
        ignore_patterns: 除外パターン

    Returns:
        再構築開始結果
    """
    index_service = get_index_service()
    paths = index_service.get_watch_paths()

    if not paths:
        return {"status": "no_paths", "message": "監視パスが登録されていません"}

    # 対象パスの決定
    if path:
        target_paths = [p for p in paths if p["path"] == path]
        if not target_paths:
            raise HTTPException(status_code=404, detail=f"パスが見つかりません: {path}")
    else:
        target_paths = paths

    # バックグラウンドで再構築開始
    for p in target_paths:
        index_service.update_path_status(p["path"], "scanning")
        background_tasks.add_task(_rebuild_path, p["path"], ignore_patterns)

    return {
        "status": "started",
        "message": f"インデックスを再構築中: {len(target_paths)}パス",
    }


async def _scan_path(path: str) -> None:
    """パスをスキャン（バックグラウンドタスク）"""
    index_service = get_index_service()

    try:
        # DBからパターンを取得し、設定とマージ
        db_patterns = index_service.get_ignore_patterns()
        patterns = list(set(settings.ignore_patterns_list + db_patterns))

        scanner = ParallelScanner(
            max_workers=settings.scan_workers,
            ignore_patterns=patterns,
            batch_size=settings.batch_size,
        )

        count = await scanner.scan_with_index_service(
            Path(path),
            index_service,
        )

        # 統計更新
        index_service.update_path_stats(path, total_files=count, indexed_files=count)
        index_service.update_path_status(path, "watching")

        # インデックス再構築
        await asyncio.get_event_loop().run_in_executor(
            None, index_service.rebuild_trigram_index
        )
        await asyncio.get_event_loop().run_in_executor(
            None, index_service.rebuild_bigram_index
        )

    except Exception as e:
        index_service.update_path_status(path, "error")
        # エラーメッセージを保存（簡略化）
        conn = index_service._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE watch_paths SET error_message = ? WHERE path = ?",
            (str(e)[:500], path),
        )
        conn.commit()


async def _rebuild_path(path: str, ignore_patterns: Optional[str] = None) -> None:
    """パスを再構築（バックグラウンドタスク）"""
    index_service = get_index_service()

    try:
        # 既存データを削除
        index_service.remove_path(path)
        index_service.register_path(path)
        index_service.update_path_status(path, "scanning")

        # 除外パターン（DB + Config + 引数）
        db_patterns = index_service.get_ignore_patterns()
        config_patterns = settings.ignore_patterns_list
        patterns = list(set(db_patterns + config_patterns))
        
        if ignore_patterns:
            arg_patterns = [p.strip() for p in ignore_patterns.split(",") if p.strip()]
            patterns.extend(arg_patterns)
        
        # 重複排除
        patterns = list(set(patterns))

        scanner = ParallelScanner(
            max_workers=settings.scan_workers,
            ignore_patterns=patterns,
            batch_size=settings.batch_size,
        )

        count = await scanner.scan_with_index_service(
            Path(path),
            index_service,
        )

        # 統計更新
        index_service.update_path_stats(path, total_files=count, indexed_files=count)
        index_service.update_path_status(path, "watching")

        # インデックス再構築
        await asyncio.get_event_loop().run_in_executor(
            None, index_service.rebuild_trigram_index
        )
        await asyncio.get_event_loop().run_in_executor(
            None, index_service.rebuild_bigram_index
        )

    except Exception as e:
        index_service.update_path_status(path, "error")
        conn = index_service._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE watch_paths SET error_message = ? WHERE path = ?",
            (str(e)[:500], path),
        )
        conn.commit()
