#!/bin/bash
# CD 部署腳本:由 self-hosted runner 在 CI 綠燈後執行(僅 main push)。
# 就地更新正式 checkout —— 資料管線(launchd bot/scanner)與 API 共用
# 此目錄的 storage/ 與 reports/,不另設部署副本。
set -euo pipefail

LIVE="${TRADING_SYSTEM_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$LIVE"

# 安全閘:只在 main 上部署;工作區有衝突時 git 會自行拒絕 pull
BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
    echo "live checkout 在 '$BRANCH' 而非 main(可能正在開發),跳過部署"
    exit 1
fi

git pull --ff-only origin main
.venv/bin/pip install -q -r requirements.txt

cd dashboard/web
npm ci --silent
npm run build
cd "$LIVE"

# 重啟 API 服務(-k:先殺再拉起)
launchctl kickstart -k "gui/$(id -u)/com.trading-system.dashboard"

echo "部署完成:$(git rev-parse --short HEAD)"
