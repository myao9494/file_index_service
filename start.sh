#!/bin/bash
#
# File Index Service 起動スクリプト
# バックエンドとフロントエンドを同時に起動
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8080
FRONTEND_PORT=5174

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== File Index Service ===${NC}"

# ポート使用中チェック
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        echo -e "${YELLOW}ポート $port が使用中です${NC}"
        read -p "プロセスを終了しますか? (y/n): " choice
        if [ "$choice" = "y" ]; then
            lsof -ti :$port | xargs kill -9 2>/dev/null || true
            echo -e "${GREEN}ポート $port を解放しました${NC}"
        else
            echo -e "${RED}起動を中止します${NC}"
            exit 1
        fi
    fi
}

# ポートチェック
check_port $BACKEND_PORT
check_port $FRONTEND_PORT

# バックエンド起動
echo -e "${GREEN}バックエンドを起動中... (ポート $BACKEND_PORT)${NC}"
cd "$SCRIPT_DIR/backend"

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}仮想環境を作成中...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

PYTHONPATH=. python -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT &
BACKEND_PID=$!

# フロントエンド起動
echo -e "${GREEN}フロントエンドを起動中... (ポート $FRONTEND_PORT)${NC}"
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}依存関係をインストール中...${NC}"
    npm install
fi

npm run dev &
FRONTEND_PID=$!

# クリーンアップ関数
cleanup() {
    echo -e "\n${YELLOW}サービスを停止中...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}停止完了${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e ""
echo -e "${GREEN}=== サービス起動完了 ===${NC}"
echo -e "管理GUI:  ${YELLOW}http://localhost:$FRONTEND_PORT${NC}"
echo -e "API:      ${YELLOW}http://localhost:$BACKEND_PORT${NC}"
echo -e ""
echo -e "停止: Ctrl+C"
echo -e ""

# プロセス待機
wait
