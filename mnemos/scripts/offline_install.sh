#!/usr/bin/env bash
# MNEMOS 服务器离线/国内镜像安装（跳过引导里的联网下载）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MECLAW2="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$MECLAW2/.." && pwd)"

export FASTEMBED_CACHE_PATH="$MECLAW2/.fastembed_cache"
export FASTEMBED_CACHE_DIR="$MECLAW2/.fastembed_cache"
export MNEMOS_OFFLINE_WHEELS="${MNEMOS_OFFLINE_WHEELS:-$MECLAW2/offline/wheels}"

# 无 offline wheels 时尝试清华镜像（可 export MNEMOS_USE_CN_MIRROR=0 关闭）
export MNEMOS_USE_CN_MIRROR="${MNEMOS_USE_CN_MIRROR:-1}"

cd "$REPO_ROOT"

echo "=== MNEMOS 离线安装 ==="
echo "项目: $MECLAW2"
echo "wheels: $MNEMOS_OFFLINE_WHEELS"
echo "模型缓存: $FASTEMBED_CACHE_PATH"
echo ""

if [[ -d "$MNEMOS_OFFLINE_WHEELS" ]] && ls "$MNEMOS_OFFLINE_WHEELS"/*.whl &>/dev/null; then
  echo ">>> 从本地 wheels 安装依赖"
  python3 -m pip install --no-index --find-links="$MNEMOS_OFFLINE_WHEELS" \
    -r "$MECLAW2/requirements.txt" \
    -r "$MECLAW2/requirements-embedding.txt"
else
  echo ">>> 未找到 offline/wheels，改用国内 pip 镜像"
  python3 -m pip install -i "${MNEMOS_PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
    -r "$MECLAW2/requirements.txt" \
    -r "$MECLAW2/requirements-embedding.txt"
fi

echo ""
echo ">>> 环境检测（跳过模型下载）"
python3 "$MECLAW2/scripts/setup_check.py" --wizard --yes --skip-embedding-download

echo ""
echo ">>> 启动命令:"
echo "  cd $REPO_ROOT"
echo "  export FASTEMBED_CACHE_PATH=$FASTEMBED_CACHE_PATH"
echo "  python3 -m uvicorn meclaw2.backend.main:app --host 0.0.0.0 --port 8766"
