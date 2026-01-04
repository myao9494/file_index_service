#!/bin/bash

# Windowsデプロイ用ビルドスクリプト (Mac上で実行)
# file_index_service用

# スクリプトのディレクトリの親ディレクトリに移動
cd "$(dirname "$0")/.."

echo "Building frontend (file_index_service)..."
cd frontend
npm run build
if [ $? -ne 0 ]; then
    echo "Frontend build failed."
    exit 1
fi
cd ..

echo "Cleaning up old static files..."
rm -rf backend/static
mkdir -p backend/static

echo "Copying frontend build to backend/static..."
cp -r frontend/dist/* backend/static/

echo "Build complete. backend/static now contains the frontend."
