"""
Everything互換検索API
- GET / でEverythingと同じ形式の検索を提供
- JSON形式のレスポンス対応
"""
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, HTMLResponse

from app.config import settings
from app.services.index_service import IndexService

router = APIRouter()


def get_index_service() -> IndexService:
    """IndexServiceインスタンスを取得"""
    service = IndexService(settings.index_db_full_path)
    return service


@router.get("/")
async def search(
    # Everything互換パラメータ
    search: Optional[str] = Query(None, alias="search", description="検索クエリ"),
    s: Optional[str] = Query(None, description="検索クエリ（エイリアス）"),
    q: Optional[str] = Query(None, description="検索クエリ（エイリアス）"),
    json: int = Query(0, alias="json", description="JSON形式で返す（1=有効）"),
    j: int = Query(0, description="JSON形式（エイリアス）"),
    offset: int = Query(0, alias="offset", ge=0, description="結果オフセット"),
    o: int = Query(0, ge=0, description="オフセット（エイリアス）"),
    count: int = Query(100, alias="count", ge=1, description="最大結果数"),
    c: int = Query(0, ge=0, description="結果数（エイリアス）"),
    sort: str = Query("name", description="ソート順（name, path, size, date_modified）"),
    ascending: int = Query(1, description="昇順(1)/降順(0)"),
    path_column: int = Query(1, description="パス列を含める"),
    size_column: int = Query(1, description="サイズ列を含める"),
    date_modified_column: int = Query(1, description="更新日列を含める"),
    # 拡張パラメータ
    path: Optional[str] = Query(None, description="検索対象パス（拡張）"),
    regex: int = Query(0, alias="regex", description="正規表現検索"),
    r: int = Query(0, description="正規表現（エイリアス）"),
    case: int = Query(0, alias="case", description="大文字小文字区別"),
    i: int = Query(0, description="大文字小文字（エイリアス）"),
    file_type: str = Query("all", description="ファイルタイプ（all/file/directory）"),
    depth: int = Query(0, description="階層深度 (0=無制限)"),
):
    """
    Everything互換検索API

    EverythingのHTTP Serverと同じパラメータをサポート。
    json=1 でJSON形式、それ以外はHTML形式で返す。
    """
    # エイリアスの解決
    query = search or s or q or ""
    use_json = json == 1 or j == 1
    result_offset = offset if offset > 0 else o
    result_count = count if c == 0 else c
    if result_count == 0:
        result_count = settings.default_count
    result_count = min(result_count, settings.max_count)

    result_count = min(result_count, settings.max_count)

    # ソート順の正規化
    sort_mapping = {
        "date_modified": "mtime",
        "size": "size",
        "path": "path",
        "name": "name",
    }
    sort_column = sort_mapping.get(sort, "name")

    # 検索実行
    index_service = get_index_service()

    try:
        results = index_service.search(
            query=query,
            path_filter=path,
            type_filter=file_type if file_type != "all" else None,
            max_results=result_count,
            offset=result_offset,
            sort=sort_column,
            ascending=ascending == 1,
            depth=depth,
        )
    finally:
        index_service.close()

    # レスポンス構築
    if use_json:
        # JSON形式
        response_results = []
        for item in results:
            result_item = {"name": item["name"]}
            if path_column:
                result_item["path"] = item["path"]
            result_item["type"] = item["type"]
            if size_column:
                result_item["size"] = item.get("size", 0)
            if date_modified_column:
                result_item["date_modified"] = item.get("mtime", 0)

            response_results.append(result_item)

        return JSONResponse(
            content={
                "totalResults": len(results),
                "results": response_results,
            }
        )
    else:
        # HTML形式（シンプルなテーブル）
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>File Index Service - Search Results</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .search-form {{ margin-bottom: 20px; }}
        input[type=text] {{ padding: 8px; width: 300px; }}
        button {{ padding: 8px 16px; }}
    </style>
</head>
<body>
    <h1>File Index Service</h1>
    <div class="search-form">
        <form method="get" action="/">
            <input type="text" name="search" value="{query}" placeholder="検索...">
            <button type="submit">検索</button>
        </form>
    </div>
    <p>検索結果: {count}件</p>
    <table>
        <tr>
            <th>名前</th>
            <th>パス</th>
            <th>タイプ</th>
            <th>サイズ</th>
        </tr>
        {rows}
    </table>
</body>
</html>
"""
        rows = ""
        for item in results:
            size_str = f"{item.get('size', 0):,}" if item["type"] == "file" else "-"
            rows += f"""
        <tr>
            <td>{item['name']}</td>
            <td>{item['path']}</td>
            <td>{item['type']}</td>
            <td>{size_str}</td>
        </tr>
"""

        html = html.format(
            query=query,
            count=len(results),
            rows=rows,
        )

        return HTMLResponse(content=html)
