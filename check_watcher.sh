#!/bin/bash
# 检查并启动自选股监控服务
if ! curl -s --max-time 3 http://localhost:8892/api/quote > /dev/null 2>&1; then
    cd /home/likilu/workspace/stock-watcher
    source .venv2/bin/activate
    nohup python3 web.py > web.log 2>&1 &
    echo "服务已重启: $(date)"
fi
