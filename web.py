#!/usr/bin/env python3
"""
自选股实时行情 - 多用户版
支持：用户登录 | 独立自选股 | 实时行情 | Excel导出
"""

import json
import http.server
import socketserver
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
from functools import wraps
import requests
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import hashlib
import secrets
import time
import os

PORT = 8892
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

USERS_FILE = DATA_DIR / "users.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

# 默认用户和自选股
DEFAULT_STOCKS = [
    {"code": "002281", "name": "光迅科技", "market": "sz"},
    {"code": "300570", "name": "太辰光", "market": "sz"},
    {"code": "300394", "name": "天孚通信", "market": "sz"},
    {"code": "300502", "name": "新易盛", "market": "sz"},
    {"code": "300308", "name": "中际旭创", "market": "sz"},
]

# 用户管理
def load_users():
    if not USERS_FILE.exists():
        # 创建默认用户 likilu
        users = {
            "likilu": {
                "password": hash_password("cao2maliki"),
                "created": datetime.now().isoformat()
            }
        }
        save_users(users)
        # 创建默认自选股
        save_user_watchlist("likilu", DEFAULT_STOCKS)
        return users
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def load_sessions():
    if not SESSIONS_FILE.exists():
        return {}
    with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_sessions(sessions):
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, ensure_ascii=False)

def create_session(username):
    sessions = load_sessions()
    token = secrets.token_urlsafe(32)
    sessions[token] = {
        "username": username,
        "created": time.time()
    }
    save_sessions(sessions)
    return token

def get_session(token):
    sessions = load_sessions()
    if token in sessions:
        # 7天过期
        if time.time() - sessions[token]["created"] < 7*24*3600:
            return sessions[token]["username"]
        else:
            del sessions[token]
            save_sessions(sessions)
    return None

def delete_session(token):
    sessions = load_sessions()
    if token in sessions:
        del sessions[token]
        save_sessions(sessions)

# 用户自选股管理
def get_user_watchlist_file(username):
    return DATA_DIR / f"watchlist_{username}.json"

def load_user_watchlist(username):
    filepath = get_user_watchlist_file(username)
    if not filepath.exists():
        return DEFAULT_STOCKS.copy()
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_user_watchlist(username, stocks):
    filepath = get_user_watchlist_file(username)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)

def load_watchlist(username):
    return load_user_watchlist(username)

def save_watchlist(username, stocks):
    save_user_watchlist(username, stocks)

# 行情获取
def get_realtime(username):
    watchlist = load_watchlist(username)
    if not watchlist:
        return []
    
    stocks = []
    codes = [f"{s['market']}{s['code']}" for s in watchlist]
    
    try:
        url = f"http://qt.gtimg.cn/q={','.join(codes)}"
        resp = requests.get(url, timeout=5)
        resp.encoding = 'gbk'
        lines = resp.text.strip().split('\n')
        
        for i, line in enumerate(lines):
            if i >= len(watchlist):
                break
            parts = line.split('~')
            if len(parts) > 10:
                stock = watchlist[i].copy()
                stock['price'] = float(parts[3]) if parts[3] else 0
                stock['yestoday'] = float(parts[4]) if parts[4] else 0
                stock['open'] = float(parts[5]) if parts[5] else 0
                stock['vol'] = float(parts[6]) if parts[6] else 0
                stock['high'] = float(parts[33]) if parts[33] else 0
                stock['low'] = float(parts[34]) if parts[34] else 0
                stock['amount'] = float(parts[37]) if parts[37] else 0
                
                if stock['yestoday'] > 0:
                    stock['change_pct'] = (stock['price'] - stock['yestoday']) / stock['yestoday'] * 100
                else:
                    stock['change_pct'] = 0
                    
                stocks.append(stock)
    except Exception as e:
        print(f"获取行情失败: {e}")
    
    return stocks

def get_stock_name(code):
    market = 'sh' if code.startswith(('6', '5', '9')) else 'sz'
    try:
        url = f"http://qt.gtimg.cn/q={market}{code}"
        resp = requests.get(url, timeout=5)
        resp.encoding = 'gbk'
        parts = resp.text.split('~')
        return parts[1] if len(parts) > 1 else code
    except:
        return code

# 指标计算
def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))

def calc_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow + signal:
        return None, None, None
    def ema(data, n):
        k = 2 / (n + 1)
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(data[i] * k + result[-1] * (1 - k))
        return result
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    dif = [ema_fast[i] - ema_slow[i] for i in range(len(ema_fast))]
    dea = ema(dif, signal)
    macd = [(dif[i] - dea[i]) * 2 for i in range(len(dif))]
    return dif[-1], dea[-1], macd[-1]

def calc_atr(kdata, period=14):
    if len(kdata) < period + 1:
        return None
    true_ranges = []
    for i in range(1, len(kdata)):
        high = float(kdata[i].get('high', 0))
        low = float(kdata[i].get('low', 0))
        prev_close = float(kdata[i-1].get('close', 0))
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return None
    return sum(true_ranges[-period:]) / period

def get_kline_data(code, market, period='day', count=100):
    try:
        url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {
            'symbol': f"{market}{code}",
            'scale': period if period != 'day' else 240,
            'ma': 'no',
            'datalen': count
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.text and resp.text != 'null':
            return resp.json()
    except Exception as e:
        print(f"获取K线失败 {code}: {e}")
    return []

# Excel导出
def export_excel(username):
    watchlist = load_watchlist(username)
    stocks = get_realtime(username)
    if not stocks:
        return None
    
    wb = openpyxl.Workbook()
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1a5276", end_color="1a5276", fill_type="solid")
    header_fill_gold = PatternFill(start_color="B7950B", end_color="B7950B", fill_type="solid")
    center = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center')
    thin = Side(style='thin', color='666666')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    green_fill = PatternFill(start_color="D5F5E3", end_color="D5F5E3", fill_type="solid")
    red_fill = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")
    gold_fill = PatternFill(start_color="FEF9E7", end_color="FEF9E7", fill_type="solid")
    blue_fill = PatternFill(start_color="D6EAF8", end_color="D6EAF8", fill_type="solid")
    
    # Sheet1: 观察池
    ws = wb.active
    ws.title = "观察池"
    headers = ['股票代码', '股票名称', '主线方向', '市场地位', '最新价', '涨跌幅', 
               '成交额', '换手率', '量比', '5日涨幅', '20日涨幅', '接近新高', '强度评分', '备注']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(1, col, h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
    
    row_num = 2
    for s in stocks:
        code = s['code']
        name = s['name']
        price = s['price']
        change_pct = s.get('change_pct', 0)
        amount = s.get('amount', 0)
        market = s.get('market', 'sz')
        
        try:
            url = f"http://qt.gtimg.cn/q={market}{code}"
            resp = requests.get(url, timeout=5)
            resp.encoding = 'gbk'
            parts = resp.text.split('~')
            turnover = float(parts[38]) if len(parts) > 38 and parts[38].replace('.', '').isdigit() else 0
            vol_ratio = float(parts[49]) if len(parts) > 49 and parts[49].replace('.', '').isdigit() else 0
        except:
            turnover = vol_ratio = 0
        
        kdata = get_kline_data(code, market, 'day', 100)
        closes = [float(d.get('close', 0)) for d in kdata] if kdata else []
        
        change_5d = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 and closes[-5] > 0 else 0
        change_20d = (closes[-1] - closes[-20]) / closes[-20] * 100 if len(closes) >= 20 and closes[-20] > 0 else 0
        near_high = "是" if len(closes) >= 60 and closes[-1] >= max(closes[-60:]) * 0.97 else "否"
        
        score = 50 + min(change_pct * 3, 20) if change_pct > 0 else 50 + max(change_pct * 3, -20)
        score += min(change_5d / 2, 15) + min(change_20d / 4, 15)
        if near_high == "是": score += 10
        if vol_ratio > 1.5: score += 5
        score = max(0, min(100, int(score)))
        
        direction = ""
        if any(x in name for x in ['光', '通信', 'CPO']): direction = "光模块"
        elif any(x in name for x in ['算力', 'AI', '智能']): direction = "AI算力"
        elif any(x in name for x in ['电', '网', '电气']): direction = "电网"
        elif any(x in name for x in ['新能', '锂', '宁德']): direction = "新能源"
        
        position = "龙头" if score >= 80 else "中军" if score >= 65 else "趋势核心" if score >= 50 else "补涨" if score >= 35 else "跟风"
        
        amount_str = f"{amount/100000000:.2f}亿" if amount >= 100000000 else f"{amount/10000:.2f}万" if amount >= 10000 else f"{amount:.0f}"
        
        row_data = [code, name, direction, position, price, 
                   f"{'+' if change_pct > 0 else ''}{change_pct:.2f}%",
                   amount_str,
                   f"{turnover:.2f}%" if turnover > 0 else "-",
                   f"{vol_ratio:.2f}" if vol_ratio > 0 else "-",
                   f"{'+' if change_5d > 0 else ''}{change_5d:.2f}%",
                   f"{'+' if change_20d > 0 else ''}{change_20d:.2f}%",
                   near_high, f"{score}分", ""]
        
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row_num, col, val)
            cell.border = border
            cell.alignment = center
            if change_pct > 0:
                cell.fill = red_fill
            elif change_pct < 0:
                cell.fill = green_fill
        
        if score >= 80:
            ws.cell(row_num, 13).fill = gold_fill
        
        row_num += 1
    
    for i, w in enumerate([12, 12, 10, 10, 10, 10, 10, 8, 8, 10, 10, 8, 10, 15], 1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = 'A2'
    
    # Sheet2: 日K
    ws_k = wb.create_sheet(title="日K")
    k_headers = ['股票代码', '日期', '开盘', '最高', '最低', '收盘', 
                 '成交量', 'MA5', 'MA10', 'MA20', 'MA60', 'RSI', 'MACD', 'ATR']
    for col, h in enumerate(k_headers, 1):
        cell = ws_k.cell(1, col, h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
    
    row_num = 2
    for s in stocks:
        code = s['code']
        market = s.get('market', 'sz')
        kdata = get_kline_data(code, market, 'day', 100)
        if kdata:
            closes = [float(d.get('close', 0)) for d in kdata]
            volumes = [float(d.get('volume', 0)) for d in kdata]
            for i, d in enumerate(kdata):
                close = closes[i]
                ma5 = sum(closes[max(0,i-4):i+1]) / min(i+1, 5) if i >= 0 else 0
                ma10 = sum(closes[max(0,i-9):i+1]) / min(i+1, 10) if i >= 0 else 0
                ma20 = sum(closes[max(0,i-19):i+1]) / min(i+1, 20) if i >= 0 else 0
                ma60 = sum(closes[max(0,i-59):i+1]) / min(i+1, 60) if i >= 0 else 0
                rsi = calc_rsi(closes[:i+1], 14) if i >= 14 else None
                dif, dea, macd = calc_macd(closes[:i+1])
                atr = calc_atr(kdata[:i+1], 14) if i >= 14 else None
                
                row_data = [code, d.get('day', ''), float(d.get('open', 0)), float(d.get('high', 0)),
                           float(d.get('low', 0)), close, volumes[i] if i < len(volumes) else 0,
                           round(ma5, 2), round(ma10, 2), round(ma20, 2), round(ma60, 2),
                           f"{rsi:.1f}" if rsi else '', f"{macd:.2f}" if macd else '', f"{atr:.2f}" if atr else '']
                
                for col, val in enumerate(row_data, 1):
                    cell = ws_k.cell(row_num, col, val)
                    cell.border = border
                    cell.alignment = center
                    if i > 0 and close >= closes[i-1]:
                        cell.fill = red_fill
                    elif i > 0:
                        cell.fill = green_fill
                row_num += 1
    
    for col in 'ABCDEFG':
        ws_k.column_dimensions[col].width = 12
    for col in 'HIJKLMN':
        ws_k.column_dimensions[col].width = 10
    ws_k.freeze_panes = 'A2'
    
    # Sheet3: 持仓
    ws_pos = wb.create_sheet(title="持仓")
    pos_headers = ['股票名称', '持仓股数', '可卖股数', '成本价', '当前价', 
                   '浮盈亏', '浮盈亏率', '仓位占比', '今日买入']
    for col, h in enumerate(pos_headers, 1):
        cell = ws_pos.cell(1, col, h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
    ws_pos.freeze_panes = 'A2'
    
    # Sheet4: 市场情绪
    ws_sent = wb.create_sheet(title="市场情绪")
    sent_headers = ['指标名称', '数值', '说明']
    for col, h in enumerate(sent_headers, 1):
        cell = ws_sent.cell(1, col, h)
        cell.font = header_font
        cell.fill = header_fill_gold
        cell.alignment = center
        cell.border = border
    
    up_count = sum(1 for s in stocks if s.get('change_pct', 0) > 0)
    down_count = sum(1 for s in stocks if s.get('change_pct', 0) < 0)
    avg_change = sum(s.get('change_pct', 0) for s in stocks) / len(stocks) if stocks else 0
    
    sentiment_data = [
        ('上涨家数', up_count, '观察池中上涨股票数'),
        ('下跌家数', down_count, '观察池中下跌股票数'),
        ('平均涨跌幅', f"{'+' if avg_change > 0 else ''}{avg_change:.2f}%", '算术平均'),
        ('最强股票', max(stocks, key=lambda x: x.get('change_pct', 0))['name'] if stocks else '-', '今日涨幅最大'),
        ('最弱股票', min(stocks, key=lambda x: x.get('change_pct', 0))['name'] if stocks else '-', '今日跌幅最大'),
        ('更新时间', datetime.now().strftime('%Y-%m-%d %H:%M'), '数据时间'),
    ]
    
    for i, (name, value, desc) in enumerate(sentiment_data, 2):
        ws_sent.cell(i, 1, name).border = border
        ws_sent.cell(i, 1).alignment = center
        ws_sent.cell(i, 2, value).border = border
        ws_sent.cell(i, 2).alignment = center
        ws_sent.cell(i, 3, desc).border = border
        ws_sent.cell(i, 3).alignment = left_align
        ws_sent.cell(i, 3).font = Font(color="888888", size=10)
    
    ws_sent.column_dimensions['A'].width = 15
    ws_sent.column_dimensions['B'].width = 20
    ws_sent.column_dimensions['C'].width = 25
    
    filename = f"观察池_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = DATA_DIR / filename
    wb.save(filepath)
    return filename

# HTML模板
HTML = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>自选股行情 - 多用户版</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; }
.header { background: linear-gradient(135deg, #1a5276, #2980b9); color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
.header h1 { font-size: 18px; }
.user-info { display: flex; align-items: center; gap: 15px; }
.user-name { font-size: 14px; opacity: 0.9; }
.logout-btn { background: rgba(255,255,255,0.2); border: none; color: white; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
.logout-btn:hover { background: rgba(255,255,255,0.3); }
.container { max-width: 1200px; margin: 0 auto; padding: 15px; }
.card { background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 15px; overflow: hidden; }
.card-header { background: #f8f9fa; padding: 12px 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
.card-header h2 { font-size: 14px; color: #333; }
.card-body { padding: 15px; }
.header-btns { display: flex; gap: 8px; flex-wrap: wrap; }
.btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.btn-primary { background: #1a5276; color: white; }
.btn-primary:hover { background: #2471a3; }
.btn-secondary { background: #27ae60; color: white; }
.btn-secondary:hover { background: #229954; }
.btn-outline { background: white; border: 1px solid #ddd; color: #666; }
.btn-outline:hover { background: #f5f5f5; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 8px; text-align: center; font-size: 13px; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; color: #666; font-weight: 500; }
.up { color: #e74c3c; }
.down { color: #27ae60; }
.loading { text-align: center; padding: 40px; color: #999; }
.hidden { display: none; }
.refresh-info { font-size: 12px; color: #888; margin-top: 10px; }
.time { font-size: 12px; color: rgba(255,255,255,0.7); }

/* 登录页面 */
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1a5276, #2980b9); }
.login-box { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); width: 100%; max-width: 380px; }
.login-box h1 { text-align: center; margin-bottom: 30px; color: #1a5276; font-size: 24px; }
.form-group { margin-bottom: 20px; }
.form-group label { display: block; margin-bottom: 8px; color: #555; font-size: 14px; }
.form-group input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.form-group input:focus { outline: none; border-color: #1a5276; }
.login-btn { width: 100%; padding: 12px; background: #1a5276; color: white; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; }
.login-btn:hover { background: #2471a3; }
.login-error { color: #e74c3c; text-align: center; margin-top: 15px; font-size: 14px; }
.demo-info { text-align: center; margin-top: 20px; color: #888; font-size: 12px; }

/* 模态框 */
.modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; padding: 25px; border-radius: 8px; width: 90%; max-width: 400px; }
.modal-header { display: flex; justify-content: space-between; margin-bottom: 20px; }
.modal-header h3 { color: #333; }
.close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #999; }
.modal-body input, .modal-body textarea { width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px; }
.modal-body textarea { height: 100px; resize: vertical; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
</style>
</head>
<body>
<div id="loginPage" class="login-page">
    <div class="login-box">
        <h1>📈 自选股行情</h1>
        <div class="form-group">
            <label>用户名</label>
            <input type="text" id="loginUsername" placeholder="请输入用户名">
        </div>
        <div class="form-group">
            <label>密码</label>
            <input type="password" id="loginPassword" placeholder="请输入密码">
        </div>
        <button class="login-btn" onclick="doLogin()">登录</button>
        <div id="loginError" class="login-error hidden"></div>
        <div class="demo-info">测试账户: likilu / cao2maliki</div>
    </div>
</div>

<div id="mainPage" class="hidden">
    <div class="header">
        <h1>📈 自选股行情</h1>
        <div class="user-info">
            <span class="user-name">👤 <span id="username"></span></span>
            <span class="time" id="updateTime"></span>
            <button class="logout-btn" onclick="logout()">退出</button>
        </div>
    </div>
    
    <div class="container">
        <div class="card">
            <div class="card-header">
                <h2>📊 观察池 (<span id="stockCount">0</span>只)</h2>
                <div class="header-btns">
                    <button class="btn btn-secondary" onclick="openAdd()">➕ 添加</button>
                    <button class="btn btn-outline" onclick="openEdit()">✏️ 编辑</button>
                    <button class="btn btn-primary" onclick="exportData()" id="exportBtn">📥 导出</button>
                </div>
            </div>
            <div class="card-body">
                <div id="loading" class="loading">加载中...</div>
                <div id="tableWrapper" class="hidden">
                    <table>
                        <thead>
                            <tr>
                                <th>代码</th>
                                <th>名称</th>
                                <th>方向</th>
                                <th>地位</th>
                                <th>现价</th>
                                <th>涨跌幅</th>
                                <th>成交额</th>
                                <th>评分</th>
                            </tr>
                        </thead>
                        <tbody id="stockTable"></tbody>
                    </table>
                </div>
                <div class="refresh-info">每30秒自动刷新 | <a href="#" onclick="refreshData(); return false;">立即刷新</a></div>
            </div>
        </div>
    </div>
</div>

<!-- 添加/编辑模态框 -->
<div id="addModal" class="modal hidden">
    <div class="modal-content">
        <div class="modal-header">
            <h3 id="modalTitle">添加股票</h3>
            <button class="close-btn" onclick="closeModal()">&times;</button>
        </div>
        <div class="modal-body">
            <div id="singleAdd">
                <input type="text" id="stockCode" placeholder="股票代码，如 600519">
                <input type="text" id="stockName" placeholder="股票名称，如 贵州茅台">
            </div>
            <div id="batchAdd" class="hidden">
                <textarea id="batchInput" placeholder="批量添加，每行格式：代码,名称
例如：
600519,贵州茅台
000858,五粮液"></textarea>
            </div>
            <label><input type="checkbox" id="batchMode"> 批量添加</label>
        </div>
        <div class="modal-footer">
            <button class="btn btn-outline" onclick="closeModal()">取消</button>
            <button class="btn btn-primary" onclick="addStock()">确定</button>
        </div>
    </div>
</div>

<!-- 编辑模态框 -->
<div id="editModal" class="modal hidden">
    <div class="modal-content">
        <div class="modal-header">
            <h3>编辑自选股</h3>
            <button class="close-btn" onclick="closeEditModal()">&times;</button>
        </div>
        <div class="modal-body">
            <div id="editList"></div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-outline" onclick="closeEditModal()">关闭</button>
        </div>
    </div>
</div>

<script>
let token = localStorage.getItem('token') || '';
let updateTimer = null;

function doLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('loginError');
    
    if (!username || !password) {
        errorEl.textContent = '请输入用户名和密码';
        errorEl.classList.remove('hidden');
        return;
    }
    
    fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username, password})
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            token = d.token;
            localStorage.setItem('token', token);
            localStorage.setItem('username', username);
            showMainPage();
        } else {
            errorEl.textContent = d.error || '登录失败';
            errorEl.classList.remove('hidden');
        }
    })
    .catch(() => {
        errorEl.textContent = '网络错误';
        errorEl.classList.remove('hidden');
    });
}

function logout() {
    fetch('/api/logout', {
        method: 'POST',
        headers: {'Authorization': token}
    });
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    token = '';
    location.reload();
}

function showMainPage() {
    document.getElementById('loginPage').classList.add('hidden');
    document.getElementById('mainPage').classList.remove('hidden');
    document.getElementById('username').textContent = localStorage.getItem('username') || '';
    loadData();
    updateTimer = setInterval(loadData, 30000);
}

function loadData() {
    fetch('/api/quote', {headers: {'Authorization': token}})
    .then(r => r.json())
    .then(d => {
        if (d.error === 'Unauthorized') {
            logout();
            return;
        }
        renderStocks(d.stocks || []);
        document.getElementById('updateTime').textContent = '更新: ' + d.time;
    });
}

function refreshData() {
    loadData();
}

function renderStocks(stocks) {
    document.getElementById('stockCount').textContent = stocks.length;
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('tableWrapper').classList.remove('hidden');
    
    const tbody = document.getElementById('stockTable');
    tbody.innerHTML = stocks.map(s => {
        const cls = s.change_pct > 0 ? 'up' : s.change_pct < 0 ? 'down' : '';
        const direction = s.direction || '-';
        const position = s.position || '-';
        const amount = s.amount >= 100000000 ? (s.amount/100000000).toFixed(2)+'亿' : (s.amount/10000).toFixed(0)+'万';
        return `<tr>
            <td>${s.code}</td>
            <td>${s.name}</td>
            <td>${direction}</td>
            <td>${position}</td>
            <td class="${cls}">${s.price}</td>
            <td class="${cls}">${s.change_pct > 0 ? '+' : ''}${s.change_pct.toFixed(2)}%</td>
            <td>${amount}</td>
            <td>${s.score || '-'}</td>
        </tr>`;
    }).join('');
}

function openAdd() {
    document.getElementById('addModal').classList.remove('hidden');
    document.getElementById('modalTitle').textContent = '添加股票';
    document.getElementById('singleAdd').classList.remove('hidden');
    document.getElementById('batchAdd').classList.add('hidden');
    document.getElementById('stockCode').value = '';
    document.getElementById('stockName').value = '';
}

function closeModal() {
    document.getElementById('addModal').classList.add('hidden');
}

function addStock() {
    const batchMode = document.getElementById('batchMode').checked;
    let stocks = [];
    
    if (batchMode) {
        const lines = document.getElementById('batchInput').value.trim().split('\\n');
        lines.forEach(line => {
            const parts = line.split(',');
            if (parts.length >= 2) {
                stocks.push({code: parts[0].trim(), name: parts[1].trim()});
            }
        });
    } else {
        const code = document.getElementById('stockCode').value.trim();
        const name = document.getElementById('stockName').value.trim() || code;
        if (code) stocks.push({code, name});
    }
    
    if (stocks.length === 0) {
        alert('请输入股票信息');
        return;
    }
    
    fetch('/api/add', {
        method: 'POST',
        headers: {'Authorization': token, 'Content-Type': 'application/json'},
        body: JSON.stringify({stocks})
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) {
            closeModal();
            loadData();
        } else {
            alert(d.error || '添加失败');
        }
    });
}

function openEdit() {
    fetch('/api/list', {headers: {'Authorization': token}})
    .then(r => r.json())
    .then(stocks => {
        const list = document.getElementById('editList');
        list.innerHTML = stocks.map(s => `<div style="padding:8px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center;">
            <span>${s.code} - ${s.name}</span>
            <button onclick="deleteStock('${s.code}')" style="color:#e74c3c;background:none;border:none;cursor:pointer;">删除</button>
        </div>`).join('');
        document.getElementById('editModal').classList.remove('hidden');
    });
}

function closeEditModal() {
    document.getElementById('editModal').classList.add('hidden');
}

function deleteStock(code) {
    if (!confirm('确定删除?')) return;
    fetch('/api/remove?code=' + code, {method: 'DELETE', headers: {'Authorization': token}})
    .then(() => openEdit())
    .then(() => loadData());
}

async function exportData() {
    const btn = document.getElementById('exportBtn');
    btn.textContent = '导出中...';
    btn.disabled = true;
    try {
        const r = await fetch('/api/export', {headers: {'Authorization': token}});
        const d = await r.json();
        if (d.success) {
            window.location.href = '/download/export';
            btn.textContent = '✅ 已导出';
            setTimeout(() => { btn.textContent = '📥 导出'; }, 3000);
        }
    } catch(e) { alert('导出失败'); }
    btn.disabled = false;
    btn.textContent = '📥 导出';
}

// 事件监听
document.getElementById('batchMode').addEventListener('change', function() {
    document.getElementById('singleAdd').classList.toggle('hidden', this.checked);
    document.getElementById('batchAdd').classList.toggle('hidden', !this.checked);
});

document.getElementById('loginPassword').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') doLogin();
});

// 页面加载
if (token) {
    showMainPage();
}

document.getElementById('loginUsername').value = localStorage.getItem('username') || '';
</script>
</body>
</html>'''

class Handler(http.server.SimpleHTTPRequestHandler):
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def get_username(self):
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
        elif 'token=' in self.path:
            token = parse_qs(urlparse(self.path).query).get('token', [''])[0]
        else:
            cookie = self.headers.get('Cookie', '')
            token = parse_qs(cookie).get('token', [''])[0] if cookie else ''
        return get_session(token)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode('utf-8'))
        
        elif path == '/api/quote':
            username = self.get_username()
            if not username:
                self.send_json({'error': 'Unauthorized'})
                return
            self.send_json({'stocks': get_realtime(username), 'time': datetime.now().strftime('%H:%M:%S')})
        
        elif path == '/api/list':
            username = self.get_username()
            if not username:
                self.send_json([])
                return
            self.send_json(load_watchlist(username))
        
        elif path.startswith('/download/'):
            import glob
            username = self.get_username()
            if not username:
                self.send_error(401)
                return
            suffix = path[10:]
            pattern = str(DATA_DIR / f"观察池_{username}_*.xlsx")
            matches = sorted(glob.glob(pattern), reverse=True)
            if matches and Path(matches[0]).exists():
                filename = Path(matches[0]).name
                self.send_response(200)
                self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{quote(filename)}")
                self.end_headers()
                with open(matches[0], 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        
        else:
            super().do_GET()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == '/api/login':
            username = data.get('username', '')
            password = data.get('password', '')
            users = load_users()
            
            if username in users and verify_password(password, users[username]['password']):
                token = create_session(username)
                self.send_json({'success': True, 'token': token, 'username': username})
            else:
                self.send_json({'success': False, 'error': '用户名或密码错误'})
        
        elif path == '/api/logout':
            auth = self.headers.get('Authorization', '')
            if auth:
                delete_session(auth)
            self.send_json({'success': True})
        
        elif path == '/api/add':
            username = self.get_username()
            if not username:
                self.send_json({'success': False, 'error': 'Unauthorized'})
                return
            
            stocks = load_watchlist(username)
            new_stocks = data.get('stocks', [])
            
            for s in new_stocks:
                code = s.get('code', '').strip()
                name = s.get('name', '').strip() or code
                market = 'sh' if code.startswith(('6', '5', '9')) else 'sz'
                
                if not any(st['code'] == code for st in stocks):
                    stocks.append({'code': code, 'name': name, 'market': market})
            
            save_watchlist(username, stocks)
            self.send_json({'success': True})
        
        elif path == '/api/export':
            username = self.get_username()
            if not username:
                self.send_json({'success': False, 'error': 'Unauthorized'})
                return
            
            filename = export_excel(username)
            if filename:
                self.send_json({'success': True, 'filename': filename})
            else:
                self.send_json({'success': False, 'error': '导出失败'})
        
        else:
            self.send_error(404)
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        username = self.get_username()
        if not username:
            self.send_json({'success': False, 'error': 'Unauthorized'})
            return
        
        if parsed.path == '/api/remove':
            params = parse_qs(parsed.query)
            code = params.get('code', [''])[0]
            stocks = load_watchlist(username)
            stocks = [s for s in stocks if s['code'] != code]
            save_watchlist(username, stocks)
            self.send_json({'success': True})
        else:
            self.send_error(404)

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', PORT), Handler) as httpd:
        print(f"╔═══════════════════════════════════════════╗")
        print(f"║  自选股行情 Web {PORT} (多用户版)              ║")
        print(f"╠═══════════════════════════════════════════╣")
        print(f"║  本机: http://localhost:{PORT}              ║")
        print(f"║  局域网: http://192.168.2.78:{PORT}        ║")
        print(f"╚═══════════════════════════════════════════╝")
        httpd.serve_forever()
