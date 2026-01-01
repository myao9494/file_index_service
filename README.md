# File Index Service

ファイルインデックス検索サービス。Everything互換APIを提供し、高速なファイル検索を実現します。

## 特徴

- **Everything互換API**: Windows版Everythingと同じHTTPインターフェース
- **高速検索**: SQLite FTS5によるトリグラム/バイグラムインデックス
- **日本語対応**: 部分一致検索（例: 「申告」→「確定申告.pdf」）
- **リアルタイム更新**: ファイル監視による自動インデックス更新
- **Web GUI**: 設定・テスト用のWebインターフェース

## クイックスタート

### 1. 依存関係のインストール

```bash
# バックエンド
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# フロントエンド
cd ../frontend
npm install
```

### 2. 起動

```bash
# バックエンド（ポート8080）
cd backend
PYTHONPATH=. python -m uvicorn app.main:app --reload --port 8080

# フロントエンド（ポート5174）
cd frontend
npm run dev
```

### 3. アクセス

- **管理GUI**: http://localhost:5174
- **API**: http://localhost:8080

## API仕様

### Everything互換検索API

```
GET /?search=クエリ&json=1
```

| パラメータ | エイリアス | 型 | デフォルト | 説明 |
|-----------|-----------|-----|-----------|------|
| search | s, q | string | "" | 検索クエリ |
| json | j | int | 0 | JSON形式（1=有効） |
| offset | o | int | 0 | 結果オフセット |
| count | c | int | 100 | 最大結果数 |
| sort | - | string | "name" | ソート順（name/path/size/date_modified） |
| ascending | - | int | 1 | 昇順(1)/降順(0) |
| path | - | string | "" | 検索対象パス（拡張） |
| file_type | - | string | "all" | all/file/directory（拡張） |

**レスポンス例:**
```json
{
  "totalResults": 42,
  "results": [
    {
      "name": "test.txt",
      "path": "/Users/example/test.txt",
      "type": "file",
      "size": 1024,
      "date_modified": 1703123456
    }
  ]
}
```

### 管理API

| メソッド | パス | 説明 |
|---------|------|------|
| GET | /status | サービスステータス取得 |
| GET | /paths | 監視パス一覧 |
| POST | /paths | 監視パス追加 |
| DELETE | /paths?path=... | 監視パス削除 |
| POST | /rebuild | インデックス再構築 |

**ステータス例:**
```json
{
  "ready": true,
  "version": "1.0.0",
  "paths": [
    {
      "path": "/Users/example",
      "status": "watching",
      "indexed_files": 5000,
      "total_files": 5000,
      "error_message": null
    }
  ],
  "total_indexed": 5000
}
```

## 設定

### 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| FILE_INDEX_HOST | 0.0.0.0 | バインドホスト |
| FILE_INDEX_PORT | 8080 | ポート番号 |
| FILE_INDEX_DATA_DIR | data | データディレクトリ |
| FILE_INDEX_DB_NAME | file_index.db | データベースファイル名 |
| FILE_INDEX_MAX_WORKERS | 4 | 並列スキャンワーカー数 |
| FILE_INDEX_BATCH_SIZE | 1000 | バッチ処理サイズ |

### 除外パターン

デフォルトで以下のパターンが除外されます:

- `node_modules`, `.git`, `.svn`
- `__pycache__`, `.pytest_cache`
- `.venv`, `venv`, `.env`
- `dist`, `build`, `.next`
- `.DS_Store`, `Thumbs.db`

## file_managerとの連携

file_managerのフロントエンドは自動的にこのサービスに接続します。

### 接続設定

file_managerの検索設定画面でサービスURLを設定できます:

1. 検索ペインの設定ボタン（⚙️）をクリック
2. 「インデックスサービスURL」に `http://localhost:8080` を入力
3. 設定は自動的にローカルストレージに保存されます

### 検索モード

| モード | 説明 | 使用API |
|--------|------|---------|
| Live | リアルタイム検索 | file_manager内部API |
| Index | 指定パス以下のインデックス検索 | 外部サービス |
| Index(ALL) | 全監視パスのインデックス検索 | 外部サービス |

## 開発

### テスト実行

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

### ビルド

```bash
cd frontend
npm run build
```

## ライセンス

MIT License

## 参考

- [Everything HTTP Server](https://www.voidtools.com/support/everything/http/)
- [SQLite FTS5](https://www.sqlite.org/fts5.html)
