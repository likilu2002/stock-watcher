import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

WATCHLIST_FILE = DATA_DIR / "watchlist.json"
HISTORY_FILE = DATA_DIR / "history"

# 默认自选股列表
DEFAULT_WATCHLIST = [
    {"code": "000001", "name": "平安银行", "market": "sz"},
    {"code": "600519", "name": "贵州茅台", "market": "sh"},
]

def load_watchlist():
    """加载自选股列表"""
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    # 如果不存在，创建默认列表
    save_watchlist(DEFAULT_WATCHLIST)
    return DEFAULT_WATCHLIST

def save_watchlist(watchlist):
    """保存自选股列表"""
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)

def add_stock(code, name, market="auto"):
    """添加自选股"""
    watchlist = load_watchlist()
    
    # 自动判断市场
    if market == "auto":
        market = "sz" if code.startswith(("00", "30")) else "sh"
    
    # 检查是否已存在
    for stock in watchlist:
        if stock["code"] == code:
            print(f"⚠️ {code} 已在自选股中")
            return False
    
    watchlist.append({"code": code, "name": name, "market": market})
    save_watchlist(watchlist)
    print(f"✅ 已添加: {code} {name}")
    return True

def remove_stock(code):
    """删除自选股"""
    watchlist = load_watchlist()
    original_len = len(watchlist)
    watchlist = [s for s in watchlist if s["code"] != code]
    
    if len(watchlist) == original_len:
        print(f"⚠️ {code} 不在自选股中")
        return False
    
    save_watchlist(watchlist)
    print(f"🗑️ 已删除: {code}")
    return True

def list_stocks():
    """列出所有自选股"""
    watchlist = load_watchlist()
    print(f"\n📋 自选股列表 (共 {len(watchlist)} 只):")
    print("-" * 40)
    for i, stock in enumerate(watchlist, 1):
        print(f"{i:2d}. {stock['code']} {stock['name']}")
    print("-" * 40)
    return watchlist

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "list":
            list_stocks()
        elif cmd == "add" and len(sys.argv) >= 4:
            add_stock(sys.argv[2], sys.argv[3])
        elif cmd == "remove" and len(sys.argv) >= 3:
            remove_stock(sys.argv[2])
    else:
        list_stocks()
