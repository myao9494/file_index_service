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
│  │  - file_metadata          │                                     │
│  │  - file_index (FTS5)      │                                     │
│  │  - file_name_index        │                                     │
│  │  - file_name_bigrams      │                                     │
│  │  - watch_paths            │                                     │
│  │  - ignore_patterns        │                                     │
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
| GET /ignores | 除外パターン一覧 |
| POST /ignores | 除外パターン追加 |
| DELETE /ignores | 除外パターン削除 |
| POST /ignores/defaults | 既定除外パターン追加 |
| POST /rebuild | インデックス再構築 |

### 2. index_service.py

SQLite FTS5を使用した高速検索エンジン。

**テーブル構造:**
```sql
-- メインファイルテーブル
CREATE TABLE file_metadata (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    parent_path TEXT NOT NULL,
    type TEXT NOT NULL,
    extension TEXT,
    size INTEGER,
    mtime REAL,
    indexed_at REAL
);

-- Everything互換向け FTS5
CREATE VIRTUAL TABLE file_index USING fts5(
    path, name, parent_path,
    content='file_metadata',
    content_rowid='id',
);

-- 3文字以上の部分一致検索向け trigram インデックス
CREATE VIRTUAL TABLE file_name_index USING fts5(
    name,
    content='file_metadata',
    content_rowid='id',
    tokenize='trigram'
);

-- 2文字検索向けバイグラムインデックス
CREATE TABLE file_name_bigrams (
    file_id INTEGER NOT NULL,
    bigram TEXT NOT NULL
);
```

**検索戦略:**
| クエリ長 | 使用インデックス |
|---------|-----------------|
| 3文字以上 | FTS5 trigram |
| 2文字 | bigram テーブル |
| 1文字 | LIKE検索 |

**検索最適化:**
- `depth` 未指定時は SQLite の `LIMIT/OFFSET` をそのまま使い、不要な行の取り込みを避ける
- 無視パターンはメモリ上でキャッシュし、watcher の高頻度判定で毎回DBを引かない
- バッチINSERTは positional parameter を使い、辞書再構築コストを減らす
- bigram は SQLite trigger で追従更新し、2文字検索でも追加直後の整合性を保つ

### 3. scanner.py

並列ファイルスキャナー。ThreadPoolExecutorで高速スキャン。

```python
# 設定
max_workers: 4  # 並列ワーカー数
batch_size: 1000  # バッチ処理サイズ
```

**高速化方針:**
- `os.scandir()` を使い、`stat()` とディレクトリ判定を `DirEntry` ベースでまとめて取得する
- ルート直下の項目も即座にバッチ投入し、再走査や取りこぼしを防ぐ
- サブディレクトリ単位の並列化は維持しつつ、バッチ flush を共通化して無駄なコピーを抑える

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
[起動 or 監視パス追加]
    ↓
[scanner.py] 並列スキャン開始
    ↓
[index_service.py] バッチ挿入
    ↓
[index_service.py] trigram / bigram 再構築
    ↓
[watcher.py] 監視開始
    ↓
[status=watching] インデックス完了
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
| File Index Service Frontend | 5174 | 開発時の管理GUI |

本番/PWAモードでは、バックエンドが `8080` で管理GUIとAPIを同時に配信します。
