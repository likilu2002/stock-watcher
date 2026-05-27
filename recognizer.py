"""
同花顺截图识别 - 批量添加自选股
支持从同花顺自选股列表截图识别股票代码
"""

import re
import json
from pathlib import Path
from typing import List, Tuple, Optional

# 尝试导入图像识别库
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️ OCR 依赖未安装 (pip install pillow pytesseract)")
    print("   备选方案：手动输入股票代码")


def recognize_stock_codes(image_path: str) -> List[Tuple[str, str]]:
    """
    从同花顺截图识别股票代码和名称
    
    Args:
        image_path: 截图文件路径
    
    Returns:
        List[(code, name), ...] 识别到的股票列表
    """
    if not OCR_AVAILABLE:
        return []
    
    try:
        img = Image.open(image_path)
        
        # 尝试不同的OCR配置
        config = '--psm 6 --oem 3'  # 假设单列文本
        
        # 执行OCR
        text = pytesseract.image_to_string(img, lang='chi_sim+eng', config=config)
        
        return parse_ths_text(text)
    
    except Exception as e:
        print(f"⚠️ OCR识别失败: {e}")
        return []


def parse_ths_text(text: str) -> List[Tuple[str, str]]:
    """
    解析同花顺截图文本，提取股票代码和名称
    
    同花顺格式特点:
    - 股票代码通常是6位数字
    - 股票名称紧跟在代码后面
    - 常见格式: "600519 贵州茅台" 或 "000001 平安银行"
    """
    stocks = []
    seen_codes = set()
    
    # 匹配 6位数字 + 空格 + 中文名称
    # 例如: 600519 贵州茅台 或 000001 平安银行
    pattern = r'(\d{6})\s+([\u4e00-\u9fa5]{2,8})(?:\s|$|[^a-zA-Z])'
    
    matches = re.findall(pattern, text)
    
    for code, name in matches:
        if code not in seen_codes and is_valid_stock_code(code):
            seen_codes.add(code)
            
            # 判断市场
            market = "sh" if code.startswith(('6', '5', '9')) else "sz"
            
            stocks.append({
                "code": code,
                "name": name.strip(),
                "market": market
            })
    
    # 备用匹配：纯数字行 (有时OCR会丢失空格)
    # 寻找连续出现的6位数字对
    raw_pattern = r'\b(\d{6})\b'
    codes_found = re.findall(raw_pattern, text)
    
    for code in codes_found:
        if code not in seen_codes and is_valid_stock_code(code):
            # 尝试在附近找中文名
            market = "sh" if code.startswith(('6', '5', '9')) else "sz"
            # 由于无法确定名称，使用代码代替
            seen_codes.add(code)
            stocks.append({
                "code": code,
                "name": code,  # 待手动确认
                "market": market
            })
    
    return stocks


def is_valid_stock_code(code: str) -> bool:
    """
    验证是否为有效的A股代码
    """
    # 主板: 600000-603999 (沪), 000000-002999 (深)
    # 科创板: 688000-689999 (沪)
    # 创业板: 300000-301999 (深)
    # 北交所: 830000-839999, 870000-879999
    
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


def recognize_from_bytes(image_bytes: bytes) -> List[dict]:
    """
    从图片字节流识别股票
    """
    if not OCR_AVAILABLE:
        return []
    
    try:
        from io import BytesIO
        img = Image.open(BytesIO(image_bytes))
        config = '--psm 6 --oem 3'
        text = pytesseract.image_to_string(img, lang='chi_sim+eng', config=config)
        return parse_ths_text(text)
    except Exception as e:
        print(f"⚠️ 字节流识别失败: {e}")
        return []


def batch_add_from_screenshot(image_path: str) -> int:
    """
    从截图批量添加到自选股
    
    Returns:
        成功添加的数量
    """
    from watchlist import load_watchlist, save_watchlist, add_stock as add_single
    
    stocks = recognize_stock_codes(image_path)
    
    if not stocks:
        print("❌ 未识别到任何股票，请检查截图质量")
        return 0
    
    print(f"\n🔍 识别到 {len(stocks)} 只股票:")
    print("-" * 40)
    
    for i, stock in enumerate(stocks, 1):
        print(f"  {i}. {stock['code']} {stock['name']}")
    
    print("-" * 40)
    
    # 添加到自选股
    watchlist = load_watchlist()
    existing_codes = {s['code'] for s in watchlist}
    added_count = 0
    
    for stock in stocks:
        if stock['code'] not in existing_codes:
            watchlist.append(stock)
            existing_codes.add(stock['code'])
            print(f"  ✅ 添加: {stock['code']} {stock['name']}")
            added_count += 1
        else:
            print(f"  ⚠️ 跳过: {stock['code']} 已在列表中")
    
    save_watchlist(watchlist)
    
    print(f"\n✨ 成功添加 {added_count} 只股票")
    return added_count


def interactive_add():
    """交互式添加股票"""
    from watchlist import add_stock, list_stocks
    
    print("\n📝 交互式添加股票")
    print("-" * 40)
    print("输入格式: 代码,名称 (例如: 600519,贵州茅台)")
    print("输入 q 退出")
    print("-" * 40)
    
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if user_input.lower() == 'q':
                break
            
            if ',' in user_input:
                code, name = user_input.split(',', 1)
                code = code.strip()
                name = name.strip()
                
                if len(code) == 6 and code.isdigit():
                    add_stock(code, name)
                else:
                    print("❌ 代码格式错误，应为6位数字")
            else:
                print("❌ 格式错误，请使用: 代码,名称")
        
        except (KeyboardInterrupt, EOFError):
            print("\n\n已退出")
            break
    
    list_stocks()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 命令行模式: python3 recognizer.py /path/to/image.png
        image_path = sys.argv[1]
        if Path(image_path).exists():
            batch_add_from_screenshot(image_path)
        else:
            print(f"❌ 文件不存在: {image_path}")
    else:
        # 交互模式
        print("""
╔════════════════════════════════════════════════════╗
║        同花顺截图识别 - 批量添加自选股              ║
╚════════════════════════════════════════════════════╝

使用方法:
1. 在同花顺软件中截取自选股列表
2. 运行: python3 recognizer.py /path/to/screenshot.png
3. 或上传截图，系统自动识别

支持的截图格式: PNG, JPG, BMP
建议分辨率: 1920x1080 或更高
        """)
