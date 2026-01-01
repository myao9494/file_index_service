# 開発ガイドライン & 仕様書

## 1. 言語設定
- **一次言語**: 日本語 (Japanese)
- **Artifacts**: 日本語で記述
- **コードコメント**: 日本語で記述
- **出力スタイル**: 簡潔かつ丁寧な日本語

## 2. 開発基本ルール
- **仕様とコードの同期**: コードを変更する際は、必ずこの `claude.md` および `docs/` 内のドキュメントも更新すること。
- **ドキュメントファースト**: `docs/` フォルダを常に整備する。適宜、Excalidraw形式の図を含める。
- **ファイル冒頭コメント**: 各ファイルの冒頭には、そのファイルの仕様を日本語のコメントで記述する。
  ```typescript
  /**
   * 2点間のユークリッド距離を計算する
   **/
  ```

## 3. 開発哲学: TDD (テスト駆動開発)
- **原則**: テスト駆動開発で進める。
- **プロセス**:
  1. 期待される入出力に基づき、**まずテストを作成する**。
  2. 実装コードは書かず、テストのみを用意する。
  3. テストを実行し、失敗を確認する (Red)。
  4. テストが正しいことを確認後、コミットする。
  5. テストをパスさせる実装を行う (Green)。
  6. すべてのテストが通過するまで繰り返す。実装中はテストを変更しない。

## 4. 環境変数設定

デフォルトの監視パスは環境変数で設定します。これにより、異なる環境（自宅macOS / 会社Windows）でも`.env`ファイルを変更するだけで動作します。

### 設定方法

1. `.env.example` を `.env` にコピー
2. `FILE_INDEX_DEFAULT_PATH` を環境に合わせて設定

### 主要な環境変数

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `FILE_INDEX_DEFAULT_PATH` | デフォルト監視パス | `/Users/username/Documents` |
| `FILE_INDEX_WATCH_PATHS` | 監視パス（カンマ区切り） | `/path1,/path2` |
| `FILE_INDEX_PORT` | サーバーポート | `8080` |

### 設定例

**macOS/Linux:**
```env
FILE_INDEX_DEFAULT_PATH=/Users/username/Documents
```

**Windows:**
```env
FILE_INDEX_DEFAULT_PATH=C:\Users\username\Documents
```

## 5. システムアーキテクチャ概要

### 全体構成
File Index Serviceは、Everything互換のファイルインデックス検索サービスです。
- **Backend (8080)**: FastAPI, SQLite FTS5
- **Frontend (5174)**: React, Vite (管理GUI)
- **連携**: file_manager (5173/8001) から利用される

### 主要コンポーネント (Backend)
- `main.py`: エントリーポイント。
- `routers/`:
  - `search.py`: 検索API (Everything互換)。
  - `admin.py`: 管理API (パス追加、再構築など)。
- `services/`:
  - `index_service.py`: SQLite FTS5を用いた検索エンジン。
  - `scanner.py`: 高速並列ファイルスキャナ。
  - `watcher.py`: watchdogを用いたファイル監視。

### 主要コンポーネント (Frontend)
- `App.tsx`: メインアプリケーション。
- `api/`: バックエンドAPIクライアント。
