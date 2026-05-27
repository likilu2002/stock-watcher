"""
A股实时行情获取模块
基于 a-stock-data 项目的技术方案
"""

import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd

# 尝试导入 mootdx，如果不可用则降级
try:
    from mootdx import quotes, financial, beststock
    MOOTDX_AVAILABLE = True
except ImportError:
    MOOTDX_AVAILABLE = False
    print("⚠️ mootdx 未安装，将使用备用方案")

import requests

class StockQuote:
    """自选股实时行情"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_realtime(self, codes: List[str], market: List[str]) -> pd.DataFrame:
        """
        获取实时行情 (使用 mootdx)
        
        Args:
            codes: 股票代码列表
            market: 市场列表 (sz/sh)
        
        Returns:
            DataFrame: 实时行情数据
        """
        if not MOOTDX_AVAILABLE:
            return self._get_realtime_fallback(codes, market)
        
        try:
            # 合并代码和市场
            symbols = [f"{m}{c}" for m, c in zip(market, codes)]
            
            # 使用 mootdx 获取行情
            client = quotes(symbol=symbols)
            df = client.realtime()
            
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print(f"⚠️ mootdx 实时行情失败: {e}")
        
        return self._get_realtime_fallback(codes, market)
    
    def _get_realtime_fallback(self, codes: List[str], market: List[str]) -> pd.DataFrame:
        """
        备用方案: 使用腾讯财经API
        """
        try:
            symbols = [f"{m}{c}" for m, c in zip(market, codes)]
            
            url = "http://qt.gtimg.cn/q="
            url += ",".join(symbols)
            
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'gbk'
            
            lines = resp.text.strip().split('\n')
            data = []
            
            for line in lines:
                if '="="' in line:
                    continue
                parts = line.split('~')
                if len(parts) > 40:
                    stock_data = {
                        'code': parts[2] if len(parts) > 2 else '',
                        'name': parts[1] if len(parts) > 1 else '',
                        'price': float(parts[3]) if parts[3].replace('.', '').isdigit() else 0,
                        'change': float(parts[31]) if parts[31].replace('.', '').isdigit() else 0,
                        'change_pct': float(parts[32]) if parts[32].replace('.', '').isdigit() else 0,
                        'volume': float(parts[36]) if parts[36].replace('.', '').isdigit() else 0,
                        'amount': float(parts[37]) if parts[37].replace('.', '').isdigit() else 0,
                        'open': float(parts[5]) if parts[5].replace('.', '').isdigit() else 0,
                        'high': float(parts[33]) if parts[33].replace('.', '').isdigit() else 0,
                        'low': float(parts[34]) if parts[34].replace('.', '').isdigit() else 0,
                        'prev_close': float(parts[4]) if parts[4].replace('.', '').isdigit() else 0,
                        'pe': float(parts[39]) if parts[39].replace('.', '').isdigit() else 0,
                        'pb': float(parts[46]) if parts[46].replace('.', '').isdigit() else 0,
                        'market_cap': float(parts[44]) if parts[44].replace('.', '').isdigit() else 0,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    data.append(stock_data)
            
            return pd.DataFrame(data)
        except Exception as e:
            print(f"⚠️ 腾讯行情API失败: {e}")
            return pd.DataFrame()
    
    def get_valuation(self, codes: List[str], market: List[str]) -> pd.DataFrame:
        """
        获取估值数据 (PE/PB/市值) 使用腾讯财经
        """
        df = self._get_realtime_fallback(codes, market)
        return df[['code', 'name', 'price', 'change', 'change_pct', 'pe', 'pb', 'market_cap']]
    
    def get_kline(self, code: str, market: str, period: str = "daily", count: int = 100) -> pd.DataFrame:
        """
        获取K线数据 (使用百度股市通)
        
        Args:
            code: 股票代码
            market: 市场 (sz/sh)
            period: K线周期 (daily/weekly/monthly)
            count: 数据条数
        """
        # 转换市场代码
        mkt_code = "0" if market == "sz" else "1"
        symbol = f"{mkt_code}{code}"
        
        period_map = {
            "daily": "kline_day",
            "weekly": "kline_week", 
            "monthly": "kline_month"
        }
        
        try:
            url = "http://quotes.baidu.com/cp/kline/market=hs"
            params = {
                "market": "hs",
                "code": symbol,
                "type": period_map.get(period, "kline_day"),
                "count": count,
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            }
            
            resp = self.session.get(url, params=params, timeout=10)
            data = resp.json()
            
            if data and 'data' in data:
                items = data['data'].get('kline', {}).get('day', [])
                df = pd.DataFrame(items, columns=['date', 'open', 'close', 'high', 'low', 'volume'])
                df = df.astype({'open': float, 'close': float, 'high': float, 'low': float, 'volume': float})
                return df
            
        except Exception as e:
            print(f"⚠️ 百度K线失败: {e}")
        
        return pd.DataFrame()


class StockWatcher:
    """自选股监控主类"""
    
    def __init__(self, watchlist_path: str = None):
        self.watchlist_path = watchlist_path
        self.quote = StockQuote()
        self.last_alert = {}  # 记录上次告警时间，防止重复
    
    def fetch_watchlist(self) -> pd.DataFrame:
        """获取自选股实时行情"""
        from watchlist import load_watchlist
        
        watchlist = load_watchlist()
        if not watchlist:
            return pd.DataFrame()
        
        codes = [s['code'] for s in watchlist]
        markets = [s['market'] for s in watchlist]
        
        df = self.quote.get_realtime(codes, markets)
        
        # 合并名称
        name_map = {s['code']: s['name'] for s in watchlist}
        df['name'] = df['code'].map(name_map)
        
        return df
    
    def format_output(self, df: pd.DataFrame) -> str:
        """格式化输出"""
        if df.empty:
            return "暂无数据"
        
        lines = []
        lines.append(f"\n📊 自选股实时行情 ({datetime.now().strftime('%H:%M:%S')})")
        lines.append("=" * 70)
        lines.append(f"{'代码':<8} {'名称':<10} {'现价':>8} {'涨跌额':>8} {'涨跌幅':>8} {'PE':>6} {'PB':>5}")
        lines.append("-" * 70)
        
        for _, row in df.iterrows():
            code = row.get('code', '')
            name = row.get('name', '')[:8]
            price = row.get('price', 0)
            change = row.get('change', 0)
            change_pct = row.get('change_pct', 0)
            pe = row.get('pe', 0)
            pb = row.get('pb', 0)
            
            # 涨跌颜色标记
            arrow = "🔴" if change > 0 else "🟢" if change < 0 else "⚪"
            sign = "+" if change >= 0 else ""
            
            lines.append(f"{code:<8} {name:<10} {price:>8.2f} {arrow}{sign}{change:>6.2f} {sign}{change_pct:>6.2f}% {pe:>6.2f} {pb:>5.2f}")
        
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def check_alerts(self, df: pd.DataFrame, threshold_pct: float = 9.0) -> List[str]:
        """检查异动并告警"""
        alerts = []
        now = time.time()
        
        for _, row in df.iterrows():
            change_pct = abs(row.get('change_pct', 0))
            code = row.get('code', '')
            
            # 涨停/跌停检测 (超过阈值)
            if change_pct >= threshold_pct:
                # 防止重复告警 (5分钟内不重复)
                if code not in self.last_alert or (now - self.last_alert[code]) > 300:
                    self.last_alert[code] = now
                    alerts.append(f"🚨 {row.get('name', code)} ({code}) 涨幅 {row.get('change_pct', 0):+.2f}%")
        
        return alerts


def main():
    """主函数"""
    watcher = StockWatcher()
    df = watcher.fetch_watchlist()
    print(watcher.format_output(df))
    
    # 检查异动
    alerts = watcher.check_alerts(df)
    if alerts:
        print("\n⚠️ 异动提醒:")
        for alert in alerts:
            print(f"  {alert}")


if __name__ == "__main__":
    main()
