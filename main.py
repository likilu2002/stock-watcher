#!/usr/bin/env python3
"""
自选股实时行情监控 - 命令行入口
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stockwatch import StockWatcher, WatchlistFile


def cmd_quote(_):
    """查看实时行情"""
    watcher = StockWatcher()
    stocks = watcher.get_realtime()
    print(watcher.format_output(stocks))
    
    alerts = watcher.check_alerts(stocks)
    if alerts:
        print("\n⚠️ 异动提醒:")
        for a in alerts:
            print(f"  {a}")


def cmd_list(_):
    """列出自选股"""
    wl = WatchlistFile()
    stocks = wl.list_all()
    print(f"\n📋 自选股列表 (共 {len(stocks)} 只):")
    print("-" * 40)
    for i, s in enumerate(stocks, 1):
        print(f"  {i:2d}. {s['code']} {s['name']} ({s['market']})")
    print("-" * 40)


def cmd_add(args):
    """添加自选股"""
    if args.interactive:
        from image_add import add_interactive
        add_interactive()
    elif args.file:
        from image_add import add_from_image
        add_from_image(args.file)
    elif args.code and args.name:
        wl = WatchlistFile()
        if wl.add(args.code, args.name):
            print(f"✅ 已添加: {args.code} {args.name}")
        else:
            print(f"⚠️ {args.code} 已在列表中")
    else:
        print("用法: main.py add <代码> <名称>")
        print("   或: main.py add -i (交互模式)")
        print("   或: main.py add -f /path/to/image.png (截图识别)")


def cmd_remove(args):
    """删除自选股"""
    wl = WatchlistFile()
    if wl.remove(args.code):
        print(f"🗑️ 已删除: {args.code}")
    else:
        print(f"⚠️ {args.code} 不在列表中")


def cmd_watch(args):
    """持续监控"""
    watcher = StockWatcher()
    interval = args.interval
    
    print(f"\n🔴 开始监控自选股 (刷新间隔: {interval}秒)")
    print("按 Ctrl+C 停止\n")
    
    try:
        while True:
            stocks = watcher.get_realtime()
            print(watcher.format_output(stocks))
            
            alerts = watcher.check_alerts(stocks)
            if alerts:
                print("\n🚨 异动告警:")
                for a in alerts:
                    print(f"  {a}")
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")


def cmd_export(args):
    """导出CSV"""
    import csv
    from datetime import datetime
    
    watcher = StockWatcher()
    stocks = watcher.get_realtime()
    
    if not stocks:
        print("❌ 无数据可导出")
        return
    
    output_file = args.output or f"watchlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['code', 'name', 'price', 'change', 'change_pct', 'pe', 'pb'])
        writer.writeheader()
        writer.writerows(stocks)
    
    print(f"✅ 已导出到: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='自选股实时行情监控',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令:
  quote              查看实时行情
  list               列出自选股
  add <代码> <名称>   添加单只股票
  add -i             交互式添加
  add -f <图片>      从截图识别添加
  remove <代码>       删除股票
  watch              持续监控
  watch -i <秒>      指定刷新间隔(默认30秒)
  export -o <文件>   导出CSV

示例:
  python3 main.py quote              # 查看行情
  python3 main.py list               # 查看列表
  python3 main.py add 000858 五粮液  # 添加股票
  python3 main.py add -i             # 交互添加
  python3 main.py watch -i 5         # 每5秒刷新
  python3 main.py export -o my.csv   # 导出
        """
    )
    
    sub = parser.add_subparsers(dest='cmd', help='命令')
    
    sub.add_parser('quote', help='查看行情')
    sub.add_parser('list', help='列出股票')
    
    # add
    add_p = sub.add_parser('add', help='添加股票')
    add_p.add_argument('code', nargs='?', help='股票代码')
    add_p.add_argument('name', nargs='?', help='股票名称')
    add_p.add_argument('-i', '--interactive', action='store_true', help='交互模式')
    add_p.add_argument('-f', '--file', help='截图文件')
    
    # remove
    rem_p = sub.add_parser('remove', help='删除股票')
    rem_p.add_argument('code', help='股票代码')
    
    # watch
    watch_p = sub.add_parser('watch', help='持续监控')
    watch_p.add_argument('-i', '--interval', type=int, default=30, help='刷新间隔(秒)')
    
    # export
    exp_p = sub.add_parser('export', help='导出CSV')
    exp_p.add_argument('-o', '--output', help='输出文件')
    
    args = parser.parse_args()
    
    if args.cmd == 'quote':
        cmd_quote(args)
    elif args.cmd == 'list':
        cmd_list(args)
    elif args.cmd == 'add':
        cmd_add(args)
    elif args.cmd == 'remove':
        cmd_remove(args)
    elif args.cmd == 'watch':
        cmd_watch(args)
    elif args.cmd == 'export':
        cmd_export(args)
    else:
        # 默认显示行情
        cmd_quote(args)


if __name__ == '__main__':
    main()