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
# 開発環境をまとめて起動
./start_dev.sh

# もしくは個別起動
# バックエンド（ポート8080）
cd backend
PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --reload --port 8080

# フロントエンド（ポート5174）
cd ../frontend
npm run dev
```

### 3. アクセス

- 開発時の管理GUI: http://localhost:5174
- API: http://localhost:8080
- 本番/PWA起動 (`./start.sh`) 時: http://localhost:8080 でGUIとAPIを同一オリジン配信

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
| depth | - | int | 0 | 階層深度。0は無制限 |

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
| GET | /ignores | 除外パターン一覧 |
| POST | /ignores | 除外パターン追加 |
| DELETE | /ignores?pattern=... | 除外パターン削除 |
| POST | /ignores/defaults | Python向け既定除外パターン追加 |
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
| FILE_INDEX_DEFAULT_PATH | OSごとのDocuments | 監視パス未指定時の既定パス |
| FILE_INDEX_WATCH_PATHS | "" | 監視対象パス（カンマ区切り） |
| FILE_INDEX_INDEX_DB_PATH | data/file_index.db | データベースファイルパス（backend基準） |
| FILE_INDEX_SCAN_WORKERS | 4 | 並列スキャンワーカー数 |
| FILE_INDEX_DEBOUNCE_MS | 500 | 監視イベントのデバウンス時間 |
| FILE_INDEX_BATCH_SIZE | 1000 | バッチ処理サイズ |
| FILE_INDEX_IGNORE_PATTERNS | .git,node_modules,.venv,__pycache__,.DS_Store | 既定の除外パターン |
| FILE_INDEX_DEFAULT_COUNT | 100 | 検索結果の既定件数 |
| FILE_INDEX_MAX_COUNT | 10000 | 検索結果の上限件数 |

### 除外パターン

デフォルトで以下のパターンが除外されます:

- `.git`
- `node_modules`
- `.venv`
- `__pycache__`
- `.DS_Store`

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
PYTHONPATH=. .venv/bin/python -m pytest tests/ -v
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
