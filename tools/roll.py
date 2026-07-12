#!/usr/bin/env python3
"""
TRPG ダイスロールツール

使用例:
  roll.py 4m6                   4個のd6を振り、MtVを算出
  roll.py 4+1m6                 4+1=5個のd6を振り、MtVを算出
  roll.py 5-2m6                 5-2=3個のd6を振り、MtVを算出
  roll.py 2d6                   2個のd6を振り、合計を算出
  roll.py 1d20+5                1d20を振り、+5の修正を加える
  roll.py d20                   1d20と同義
  roll.py 4m6 6m6 2d6           複数指定OK
  roll.py -n 3 4m6              4m6を3回振る

NM6 ノーテーションは d6 のみ対応。
通常ダイスは d4, d6, d8, d10, d12, d20, d100 に対応。
"""

import argparse
import random
import re
import sys

VALID_DICE_SIZES = {4, 6, 8, 10, 12, 20, 100}
M6_PATTERN = re.compile(r'^(\d+)([+-]\d+)?m6$', re.IGNORECASE)
D_PATTERN = re.compile(r'^(\d*)d(\d+)([+-]\d+)?$', re.IGNORECASE)


def roll_m6(n):
    """n個のd6を振り、出目(ソート済)とMtVを返す"""
    rolls = sorted(random.randint(1, 6) for _ in range(n))
    counts = {}
    for r in rolls:
        counts[r] = counts.get(r, 0) + 1
    mtv = max(counts.values())
    return rolls, mtv


def roll_dn(count, size):
    """count個のd{size}を振り、出目と合計を返す"""
    rolls = [random.randint(1, size) for _ in range(count)]
    return rolls, sum(rolls)


def format_modifier(mod):
    if mod == 0:
        return ""
    return f"{mod:+d}"


def parse_and_roll(notation):
    """ノーテーションをパースしてロールを実行、結果文字列を返す"""
    m = M6_PATTERN.match(notation)
    if m:
        base = int(m.group(1))
        mod = int(m.group(2)) if m.group(2) else 0
        total = base + mod
        if total <= 1:
            return f"{notation} → ダイス数 {total} → 自動失敗"
        rolls, mtv = roll_m6(total)
        return f"{notation} → ({total}d6) {rolls} → MtV {mtv}"

    m = D_PATTERN.match(notation)
    if m:
        count_str = m.group(1)
        count = int(count_str) if count_str else 1
        size = int(m.group(2))
        mod = int(m.group(3)) if m.group(3) else 0
        if size not in VALID_DICE_SIZES:
            return (
                f"{notation} → エラー: d{size} は対応外 "
                f"(対応: d4, d6, d8, d10, d12, d20, d100)"
            )
        if count <= 0:
            return f"{notation} → エラー: ダイス数は1以上"
        rolls, total = roll_dn(count, size)
        result = total + mod
        mod_str = format_modifier(mod)
        if mod_str:
            return f"{notation} → {rolls} = {total} {mod_str} → {result}"
        return f"{notation} → {rolls} → {total}"

    return f"{notation} → エラー: 不正なノーテーション"


def main():
    parser = argparse.ArgumentParser(
        description="TRPGダイスロールツール (NM6 / dN 両対応)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("rolls", nargs="+", help="ダイスノーテーション")
    parser.add_argument("-n", "--count", type=int, default=1,
                        help="各ノーテーションの試行回数 (デフォルト: 1)")
    args = parser.parse_args()

    if args.count < 1:
        print("エラー: -n は1以上の整数", file=sys.stderr)
        sys.exit(1)

    for notation in args.rolls:
        if args.count > 1:
            print(f"=== {notation} × {args.count} ===")
            for i in range(args.count):
                print(f"  {i+1}: {parse_and_roll(notation)}")
        else:
            print(parse_and_roll(notation))


if __name__ == "__main__":
    main()
