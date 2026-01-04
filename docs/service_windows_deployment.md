# File Index Service Windows環境へのデプロイガイド

このガイドでは、フロントエンドのビルド環境（Node.js/npm）がないWindows環境で、File Index Serviceアプリを使用する方法を説明します。

## 概要

開発機（Mac/Linux）でフロントエンドをビルドし、その成果物をバックエンド（Python/FastAPI）に同梱して配布します。Windows側ではPython環境のみで動作します。

## 手順

### 1. 開発機での準備（ビルド）

1. `file_index_service` ディレクトリで以下のスクリプトを実行します。

   ```bash
   ./scripts/build_service_for_windows.sh
   ```

   これにより、フロントエンドがビルドされ、バックエンドの `backend/static` にコピーされます。

2. Windows機に `backend` フォルダと `start_service_windows.bat` をコピーします。

### 2. Windows環境での実行

1. `start_service_windows.bat` をダブルクリックします。
2. サーバーが起動したら、ブラウザで `http://localhost:8080` にアクセスします。

## 注意事項

- 本番モードでは、API (`/status`, `/search`, etc.) はルートパス (`/`) と同じオリジンで提供されます。
- `http://localhost:8080` にアクセスすると、React製の管理画面が表示されます。
- `http://localhost:8080/?search=...&json=1` でJSON APIにアクセスできます（Everything互換）。
- `http://localhost:8080/?search=...` (jsonなし) は管理画面 (`index.html`) を返します。

## 構成

- `frontend/src/App.tsx`: ビルド時はAPI URLを相対パスに切り替えます。
- `backend/app/routers/search.py`: `json=1` 以外のリクエストに対して、ビルド済みの `index.html` を返すように変更されています。
