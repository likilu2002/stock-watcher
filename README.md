# 自选股实时行情监控

基于腾讯财经API的自选股监控系统，支持命令行和Web界面。

## 功能特点

- 📊 **实时行情** — 价格、涨跌幅、PE/PB等指标
- 🔍 **截图识别** — 从同花顺截图批量添加股票
- 🌐 **Web界面** — 浏览器查看，支持增删自选股
- ⏰ **定时监控** — 自动刷新，支持异动告警
- 📁 **数据导出** — CSV格式导出

## 快速开始

### 命令行模式

```bash
cd /home/likilu/workspace/stock-watcher

# 查看自选股列表
python3 main.py list

# 查看实时行情
python3 main.py quote

# 添加股票
python3 main.py add 600519 贵州茅台

# 删除股票
python3 main.py remove 600519

# 持续监控 (每30秒刷新)
python3 main.py watch

# 指定刷新间隔
python3 main.py watch -i 5

# 导出CSV
python3 main.py export -o my_stocks.csv
```

### Web界面模式

```bash
python3 web.py
```

然后访问:
- 本机: http://localhost:8888
- 局域网: http://192.168.2.78:8888

## 添加股票

### 手动添加
```bash
python3 main.py add 000858 五粮液
```

### 交互模式
```bash
python3 main.py add -i
# 然后输入: 300750,宁德时代
```

### 截图识别 (需要安装OCR)
```bash
# 安装tesseract
sudo apt install tesseract-ocr

# 截图后识别添加
python3 image_add.py /path/to/screenshot.png
```

## 开机自启动

Web界面已配置为开机自启动 (cron @reboot)

## 数据文件

- 自选股列表: `data/watchlist.json`
- 导出文件: `data/*.csv`

## 依赖

- Python 3.x
- requests

安装依赖:
```bash
pip install requests
```
