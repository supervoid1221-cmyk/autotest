#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "用法：$0 <dist目录> <SSH私钥> <部署主机> <部署根目录>" >&2
  exit 2
fi

dist_dir=${1%/}
ssh_key=$2
deploy_host=$3
deploy_root=${4%/}

if [ ! -f "$dist_dir/index.html" ] || [ ! -d "$dist_dir/assets" ]; then
  echo "前端构建产物不完整：$dist_dir" >&2
  exit 2
fi

# 不删除旧版哈希资源：已打开的页面仍可能在稍后动态加载旧版路由模块。
# 先上传资源，最后原子替换 index.html，避免入口引用尚未传完的新资源。
rsync -az --exclude='/index.html' \
  -e "ssh -i $ssh_key -o BatchMode=yes" \
  "$dist_dir/" "$deploy_host:$deploy_root/frontend-dist/"
rsync -az -e "ssh -i $ssh_key -o BatchMode=yes" \
  "$dist_dir/index.html" "$deploy_host:$deploy_root/frontend-dist/.index.html.next"
ssh -i "$ssh_key" -o BatchMode=yes "$deploy_host" \
  "mv -f '$deploy_root/frontend-dist/.index.html.next' '$deploy_root/frontend-dist/index.html'"
