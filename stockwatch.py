"""
自选股实时行情监控 - 纯HTTP版本
不需要mootdx/pandas，直接调用腾讯/百度API
"""

import json
import time
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import requests

# 数据目录
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
WATCHLIST_FILE = DATA_DIR / "watchlist.json"


class WatchlistFile:
    """自选股文件管理"""
    
    def __init__(self, filepath: Path = None):
        self.filepath = filepath or WATCHLIST_FILE
    
    def load(self) -> List[Dict]:
        """加载自选股"""
        if self.filepath.exists():
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save(self, watchlist: List[Dict]):
        """保存自选股"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    
    def add(self, code: str, name: str) -> bool:
        """添加股票"""
        watchlist = self.load()
        for s in watchlist:
            if s['code'] == code:
                return False
        
        market = "sh" if code.startswith(('6', '5', '9')) else "sz"
        watchlist.append({"code": code, "name": name, "market": market})
        self.save(watchlist)
        return True
    
    def remove(self, code: str) -> bool:
        """删除股票"""
        watchlist = self.load()
        original = len(watchlist)
        watchlist = [s for s in watchlist if s['code'] != code]
        if len(watchlist) < original:
            self.save(watchlist)
            return True
        return False
    
    def list_all(self) -> List[Dict]:
        """列出所有"""
        return self.load()


class StockWatcher:
    """自选股监控主类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def load_watchlist(self) -> List[Dict]:
        """加载自选股"""
        if WATCHLIST_FILE.exists():
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        # 默认列表
        return [
            {"code": "000001", "name": "平安银行", "market": "sz"},
            {"code": "600519", "name": "贵州茅台", "market": "sh"},
        ]
    
    def save_watchlist(self, watchlist: List[Dict]):
        """保存自选股"""
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    
    def get_realtime(self) -> List[Dict]:
        """
        获取自选股实时行情
        使用腾讯财经API
        """
        watchlist = self.load_watchlist()
        if not watchlist:
            return []
        
        # 构建腾讯API的股票代码
        symbols = [f"{s['market']}{s['code']}" for s in watchlist]
        
        try:
            url = "http://qt.gtimg.cn/q=" + ",".join(symbols)
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'gbk'
            
            stocks_data = []
            lines = resp.text.strip().split('\n')
            
            for i, line in enumerate(lines):
                if '="="' in line or not line.strip():
                    continue
                
                parts = line.split('~')
                if len(parts) < 40:
                    continue
                
                stock = watchlist[i] if i < len(watchlist) else {}
                
                data = {
                    'code': parts[2] if len(parts) > 2 else stock.get('code', ''),
                    'name': stock.get('name', parts[1] if len(parts) > 1 else ''),
                    'price': float(parts[3]) if parts[3].replace('.', '').isdigit() else 0,
                    'prev_close': float(parts[4]) if parts[4].replace('.', '').isdigit() else 0,
                    'open': float(parts[5]) if parts[5].replace('.', '').isdigit() else 0,
                    'volume': float(parts[36]) if parts[36].replace('.', '').isdigit() else 0,
                    'amount': float(parts[37]) if parts[37].replace('.', '').isdigit() else 0,
                    'high': float(parts[33]) if parts[33].replace('.', '').isdigit() else 0,
                    'low': float(parts[34]) if parts[34].replace('.', '').isdigit() else 0,
                    'pe': float(parts[39]) if parts[39].replace('.', '').isdigit() else 0,
                    'pb': float(parts[46]) if parts[46].replace('.', '').isdigit() else 0,
                    'change': 0,
                    'change_pct': 0,
                }
                
                # 计算涨跌
                if data['prev_close'] > 0:
                    data['change'] = data['price'] - data['prev_close']
                    data['change_pct'] = (data['change'] / data['prev_close']) * 100
                
                stocks_data.append(data)
            
            return stocks_data
        
        except Exception as e:
            print(f"❌ 获取行情失败: {e}")
            return []
    
    def format_output(self, stocks: List[Dict]) -> str:
        """格式化输出"""
        if not stocks:
            return "暂无数据"
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        lines = []
        lines.append(f"\n📊 自选股实时行情 ({now})")
        lines.append("=" * 75)
        lines.append(f"{'代码':<8} {'名称':<10} {'现价':>9} {'涨跌额':>9} {'涨跌幅':>10} {'PE':>8} {'PB':>6}")
        lines.append("-" * 75)
        
        for s in stocks:
            code = s.get('code', '')
            name = s.get('name', '')[:8]
            price = s.get('price', 0)
            change = s.get('change', 0)
            change_pct = s.get('change_pct', 0)
            pe = s.get('pe', 0)
            pb = s.get('pb', 0)
            
            # 涨跌标记
            if change > 0:
                arrow = "🔴"
                sign = "+"
            elif change < 0:
                arrow = "🟢"
                sign = ""
            else:
                arrow = "⚪"
                sign = ""
            
            pe_str = f"{pe:.2f}" if pe > 0 else "-"
            pb_str = f"{pb:.2f}" if pb > 0 else "-"
            
            lines.append(
                f"{code:<8} {name:<10} {price:>9.2f} {arrow}{sign}{change:>8.2f} "
                f"{sign}{change_pct:>9.2f}% {pe_str:>8} {pb_str:>6}"
            )
        
        lines.append("=" * 75)
        
        # 统计
        up_count = sum(1 for s in stocks if s.get('change', 0) > 0)
        down_count = sum(1 for s in stocks if s.get('change', 0) < 0)
        lines.append(f"   上涨: {up_count}  下跌: {down_count}  平盘: {len(stocks) - up_count - down_count}")
        
        return "\n".join(lines)
    
    def check_alerts(self, stocks: List[Dict], threshold_pct: float = 9.0) -> List[str]:
        """检查异动"""
        alerts = []
        now = time.time()
        
        for s in stocks:
            change_pct = abs(s.get('change_pct', 0))
            code = s.get('code', '')
            
            if change_pct >= threshold_pct:
                if code not in self.last_alert or (now - self.last_alert.get(code, 0)) > 300:
                    self.last_alert[code] = now
                    direction = "涨停" if s.get('change', 0) > 0 else "跌停"
                    alerts.append(
                        f"🚨 {s.get('name', code)} ({code}) {direction} {s.get('change_pct', 0):+.2f}%"
                    )
        
        return alerts
    
    # 简单内存存储上次告警时间
    last_alert: Dict[str, float] = {}


def list_stocks():
    """列出自选股"""
    watcher = StockWatcher()
    watchlist = watcher.load_watchlist()
    
    print(f"\n📋 自选股列表 (共 {len(watchlist)} 只):")
    print("-" * 40)
    for i, stock in enumerate(watchlist, 1):
        print(f"  {i:2d}. {stock['code']} {stock['name']} ({stock['market']})")
    print("-" * 40)


def add_stock(code: str, name: str):
    """添加自选股"""
    watcher = StockWatcher()
    watchlist = watcher.load_watchlist()
    
    # 自动判断市场
    if code.startswith(('6', '5', '9')):
        market = 'sh'
    else:
        market = 'sz'
    
    # 检查重复
    for s in watchlist:
        if s['code'] == code:
            print(f"⚠️ {code} 已在自选股中")
            return False
    
    watchlist.append({"code": code, "name": name, "market": market})
    watcher.save_watchlist(watchlist)
    print(f"✅ 已添加: {code} {name} ({market})")
    return True


def remove_stock(code: str):
    """删除自选股"""
    watcher = StockWatcher()
    watchlist = watcher.load_watchlist()
    
    original_len = len(watchlist)
    watchlist = [s for s in watchlist if s['code'] != code]
    
    if len(watchlist) == original_len:
        print(f"⚠️ {code} 不在自选股中")
        return False
    
    watcher.save_watchlist(watchlist)
    print(f"🗑️ 已删除: {code}")
    return True


def main():
    """主函数"""
    watcher = StockWatcher()
    stocks = watcher.get_realtime()
    print(watcher.format_output(stocks))
    
    # 检查异动
    alerts = watcher.check_alerts(stocks)
    if alerts:
        print("\n⚠️ 异动提醒:")
        for alert in alerts:
            print(f"  {alert}")


if __name__ == "__main__":
    main()
