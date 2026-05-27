#!/usr/bin/env python3
"""
同花顺截图识别 - 批量添加自选股
直接调用tesseract命令行，无需pytesseract
"""

import re
import json
import sys
import subprocess
from pathlib import Path
from typing import List, Dict


DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
WATCHLIST_FILE = DATA_DIR / "watchlist.json"


def ocr_image(image_path: str) -> str:
    """使用tesseract直接识别图片"""
    try:
        result = subprocess.run(
            ['tesseract', image_path, 'stdout', '-l', 'chi_sim', '--psm', '6', '--oem', '3'],
            capture_output=True,
            text=True,
            timeout=30
        )
        # 如果中文识别失败，尝试纯英文
        if not result.stdout.strip():
            result = subprocess.run(
                ['tesseract', image_path, 'stdout', '-l', 'eng', '--psm', '6'],
                capture_output=True,
                text=True,
                timeout=30
            )
        return result.stdout
    except Exception as e:
        print(f"❌ OCR失败: {e}")
        return ""


def parse_stock_text(text: str) -> List[Dict]:
    """
    解析股票代码和名称
    格式: 600519 贵州茅台 或 000001 平安银行
    """
    stocks = []
    seen_codes = set()
    
    # 主要模式: 代码 + 空格 + 中文名
    pattern = r'(\d{6})\s+([\u4e00-\u9fa5]{2,8})(?:\s|$|[^a-zA-Z])'
    matches = re.findall(pattern, text)
    
    for code, name in matches:
        if code not in seen_codes and is_valid_code(code):
            seen_codes.add(code)
            market = "sh" if code.startswith(('6', '5', '9')) else "sz"
            stocks.append({"code": code, "name": name.strip(), "market": market})
    
    # 备用模式: 纯6位数字行
    if not stocks:
        pattern2 = r'\b(\d{6})\b'
        codes = re.findall(pattern2, text)
        for code in codes:
            if code not in seen_codes and is_valid_code(code):
                seen_codes.add(code)
                market = "sh" if code.startswith(('6', '5', '9')) else "sz"
                stocks.append({"code": code, "name": code, "market": market})
    
    return stocks


def is_valid_code(code: str) -> bool:
    """验证A股代码有效性"""
    valid_ranges = [
        ('600000', '603999'),  # 沪市主板
        ('688000', '689999'),  # 科创板
        ('000000', '002999'),  # 深市主板
        ('300000', '301999'),  # 创业板
        ('830000', '839999'),  # 北交所
        ('870000', '879999'),  # 北交所
    ]
    for start, end in valid_ranges:
        if start <= code <= end:
            return True
    return False


def load_watchlist() -> List[Dict]:
    """加载自选股"""
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_watchlist(watchlist: List[Dict]):
    """保存自选股"""
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


def add_from_image(image_path: str) -> int:
    """从截图批量添加"""
    if not Path(image_path).exists():
        print(f"❌ 文件不存在: {image_path}")
        return 0
    
    print(f"🔍 正在识别图片: {image_path}")
    text = ocr_image(image_path)
    
    if not text.strip():
        print("❌ 未识别到文字内容")
        return 0
    
    # 调试: 打印识别的文字
    print(f"\n📝 识别到的文字 (前500字):\n{text[:500]}...\n")
    
    stocks = parse_stock_text(text)
    
    if not stocks:
        print("❌ 未识别到有效股票代码")
        print("提示: 请确保截图清晰，股票代码和名称在同一行")
        return 0
    
    print(f"\n✅ 识别到 {len(stocks)} 只股票:")
    print("-" * 40)
    for s in stocks:
        print(f"  {s['code']} {s['name']}")
    
    # 添加到自选股
    watchlist = load_watchlist()
    existing = {s['code'] for s in watchlist}
    added = 0
    
    for s in stocks:
        if s['code'] not in existing:
            watchlist.append(s)
            existing.add(s['code'])
            print(f"  ✅ 添加: {s['code']} {s['name']}")
            added += 1
        else:
            print(f"  ⚠️ 跳过: {s['code']} 已在列表")
    
    save_watchlist(watchlist)
    print(f"\n✨ 共添加 {added} 只股票")
    return added


def interactive_add():
    """交互式添加"""
    print("\n📝 交互式添加股票")
    print("-" * 40)
    print("格式: 代码,名称 (例如: 600519,贵州茅台)")
    print("输入 q 退出\n")
    
    while True:
        try:
            user_input = input("> ").strip()
            if user_input.lower() == 'q':
                break
            if ',' in user_input:
                code, name = user_input.split(',', 1)
                code = code.strip()
                name = name.strip()
                if len(code) == 6 and code.isdigit() and is_valid_code(code):
                    watchlist = load_watchlist()
                    if code not in {s['code'] for s in watchlist}:
                        market = "sh" if code.startswith(('6', '5', '9')) else "sz"
                        watchlist.append({"code": code, "name": name, "market": market})
                        save_watchlist(watchlist)
                        print(f"  ✅ 已添加: {code} {name}")
                    else:
                        print(f"  ⚠️ {code} 已在列表")
                else:
                    print("  ❌ 代码格式错误，应为6位有效A股代码")
            else:
                print("  ❌ 格式错误，使用: 代码,名称")
        except (KeyboardInterrupt, EOFError):
            print("\n已退出")
            break


if __name__ == "__main__":
    if len(sys.argv) > 1:
        add_from_image(sys.argv[1])
    else:
        print("""
╔════════════════════════════════════════════════════╗
║        同花顺截图识别 - 批量添加自选股              ║
╚════════════════════════════════════════════════════╝

使用方法:
  python3 image_add.py /path/to/screenshot.png

示例:
  python3 image_add.py ~/Desktop/stocks.png

提示:
  - 截图分辨率越高越好
  - 确保股票代码清晰可见
  - 支持中英文混合识别
        """)