# File Index Service アーキテクチャ

## システム概要

File Index ServiceはEverything互換のファイルインデックス検索サービスです。

```
┌─────────────────────────────────────────────────────────────────────┐
│                         クライアント                                  │
├───────────────────────┬───────────────────────┬─────────────────────┤
│   file_manager        │   管理GUI (5174)      │   Everything互換    │
│   (5173)              │                       │   クライアント       │
└───────────┬───────────┴───────────┬───────────┴──────────┬──────────┘
            │                       │                      │
            └───────────────────────┼──────────────────────┘
                                    │ HTTP
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    File Index Service (8080)                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      FastAPI Router                          │   │
│  ├───────────────────────────┬─────────────────────────────────┤   │
│  │   search.py               │   admin.py                      │   │
│  │   - GET / (検索)          │   - GET /status                 │   │
│  │   - Everything互換API     │   - GET/POST/DELETE /paths      │   │
│  │                           │   - POST /rebuild               │   │
│  └─────────────┬─────────────┴──────────────┬──────────────────┘   │
│                │                            │                       │
│  ┌─────────────▼─────────────┐  ┌──────────▼──────────────────┐   │
│  │     index_service.py      │  │       watcher.py            │   │
│  │  - SQLite FTS5インデックス │  │  - ファイル変更監視          │   │
│  │  - trigram/bigram検索     │  │  - watchdog統合             │   │
│  └─────────────┬─────────────┘  └──────────────────────────────┘   │
│                │                                                    │
│  ┌─────────────▼─────────────┐                                     │
│  │       scanner.py          │                                     │
│  │  - 並列ファイルスキャン    │                                     │
│  │  - ThreadPoolExecutor     │                                     │
│  └───────────────────────────┘                                     │
├─────────────────────────────────────────────────────────────────────┤
│                          data/                                      │
│  ┌───────────────────────────┐                                     │
│  │    file_index.db          │                                     │
│  │  - files テーブル         │                                     │
│  │  - files_fts (FTS5)       │                                     │
│  │  - files_bigram           │                                     │
│  │  - watch_paths            │                                     │
│  └───────────────────────────┘                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## コンポーネント詳細

### 1. FastAPI Router

#### search.py - Everything互換検索API

```
GET /?search=query&json=1
```

Everything HTTPサーバーと同じパラメータをサポート:
- `search`/`s`/`q`: 検索クエリ
- `json`/`j`: JSON形式出力
- `offset`/`o`: オフセット
- `count`/`c`: 最大件数
- `sort`: ソート順
- `ascending`: 昇順/降順

#### admin.py - 管理API

| エンドポイント | 機能 |
|---------------|------|
| GET /status | サービスステータス |
| GET /paths | 監視パス一覧 |
| POST /paths | パス追加 |
| DELETE /paths | パス削除 |
| POST /rebuild | インデックス再構築 |

### 2. index_service.py

SQLite FTS5を使用した高速検索エンジン。

**テーブル構造:**
```sql
-- メインファイルテーブル
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    size INTEGER DEFAULT 0,
    date_modified REAL DEFAULT 0,
    parent_path TEXT
);

-- FTS5インデックス（トリグラム）
CREATE VIRTUAL TABLE files_fts USING fts5(
    name, path,
    content='files',
    content_rowid='id',
    tokenize='trigram'
);

-- バイグラムインデックス
CREATE TABLE files_bigram (
    file_id INTEGER,
    bigram TEXT,
    position INTEGER
);
```

**検索戦略:**
| クエリ長 | 使用インデックス |
|---------|-----------------|
| 3文字以上 | FTS5 trigram |
| 2文字 | bigram テーブル |
| 1文字 | LIKE検索 |

### 3. scanner.py

並列ファイルスキャナー。ThreadPoolExecutorで高速スキャン。

```python
# 設定
max_workers: 4  # 並列ワーカー数
batch_size: 1000  # バッチ処理サイズ
```

### 4. watcher.py

watchdogを使用したファイル監視。

```python
# 監視イベント
on_created → インデックス追加
on_deleted → インデックス削除
on_modified → インデックス更新
on_moved → パス更新
```

## データフロー

### 1. インデックス構築フロー

```
[監視パス追加]
    ↓
[scanner.py] 並列スキャン開始
    ↓
[index_service.py] バッチ挿入
    ↓
[watcher.py] 監視開始
    ↓
[ready: true] インデックス完了
```

### 2. 検索フロー

```
[クライアント] GET /?search=test&json=1
    ↓
[search.py] パラメータ解析
    ↓
[index_service.py]
    ├─ クエリ長判定
    ├─ インデックス選択（FTS5/bigram/LIKE）
    └─ 検索実行
    ↓
[search.py] 結果フォーマット
    ↓
[クライアント] JSON応答
```

### 3. リアルタイム更新フロー

```
[ファイル変更]
    ↓
[watcher.py] イベント検知
    ↓
[index_service.py] インデックス更新
    ↓
[次回検索] 更新結果反映
```

## file_managerとの連携

```
┌──────────────────────────────────────────────────────────────┐
│                    file_manager (5173)                        │
├───────────────────────────────────────────────────────────────┤
│  FileSearch.tsx                                               │
│  ├─ Live モード → 内部API (/api/search)                      │
│  └─ Index/Index(ALL) モード → 外部サービス (8080)            │
│                                                               │
│  indexService.ts                                              │
│  ├─ getIndexServiceUrl()                                      │
│  ├─ searchIndexService()                                      │
│  └─ getIndexServiceStatus()                                   │
└──────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP (port 8080)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                 File Index Service (8080)                     │
└──────────────────────────────────────────────────────────────┘
```

## ポート構成

| サービス | ポート | 用途 |
|---------|-------|------|
| file_manager Backend | 8001 | ファイル操作API |
| file_manager Frontend | 5173 | ファイルマネージャーUI |
| File Index Service Backend | 8080 | インデックス検索API |
| File Index Service Frontend | 5174 | 管理GUI |
