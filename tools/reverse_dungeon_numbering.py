#!/usr/bin/env python3
"""
ダンジョンナンバリング反転

dungeon_image_builder.py 形式の ASCII Art について、
Rn / Pn / Sn のラベル番号を逆順に置換する (1 ↔ max, 2 ↔ max-1, ...) 。

セル幅 6 は維持するため、桁数の差分は前後のスペース/ダッシュで吸収する。

使い方:
    python3 tools/reverse_dungeon_numbering.py input.txt -o output.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


LABEL_RE = re.compile(r'\b([RPSHE])(\d{1,3})\b')
ROOM_BOX_RE = re.compile(r'\|([ R\d]{4})\|')
HCORRIDOR_RE = re.compile(r'(-+)([PH]\d{1,3})(-+)')
CELL_LABEL_RE = re.compile(r'^(\s*)([PSHE]\d{1,3})(\s*)$')


def find_max_per_prefix(text: str) -> dict[str, int]:
    max_per: dict[str, int] = {}
    for m in LABEL_RE.finditer(text):
        prefix = m.group(1)
        n = int(m.group(2))
        if n > max_per.get(prefix, 0):
            max_per[prefix] = n
    return max_per


def reverse_label(label: str, max_per: dict[str, int]) -> str:
    prefix = label[0]
    n = int(label[1:])
    return f'{prefix}{max_per[prefix] + 1 - n}'


def format_room(label: str) -> str:
    if len(label) == 2:
        return f'| {label} |'
    if len(label) == 3:
        return f'|{label} |'
    if len(label) == 4:
        return f'|{label}|'
    raise ValueError(f"label too long: {label}")


def format_hcorr(label: str, total_w: int) -> str:
    extra = total_w - len(label)
    if extra < 0:
        sys.stderr.write(f"warning: '{label}' を幅 {total_w} に収められません\n")
        return label
    # dungeon_builder.py の慣習に合わせる: 3 桁ラベルは leading 1, trailing 2
    if len(label) == 3 and total_w == 6:
        return '-' + label + '--'
    leading = (extra + 1) // 2
    trailing = extra - leading
    return '-' * leading + label + '-' * trailing


def format_vert_cell(label: str) -> str:
    if len(label) == 2:
        return f'  {label}  '
    if len(label) == 3:
        return f' {label}  '
    if len(label) == 4:
        return f' {label} '
    raise ValueError(f"label too long: {label}")


def transform_line(line: str, max_per: dict[str, int]) -> str:
    # 1) 部屋ボックス: |XXXX|
    def repl_room(m: re.Match) -> str:
        content = m.group(1).strip()
        if not re.match(r'^R\d{1,3}$', content):
            return m.group(0)
        return format_room(reverse_label(content, max_per))
    line = ROOM_BOX_RE.sub(repl_room, line)

    # 2) 横通路: -+Pn-+
    def repl_hcorr(m: re.Match) -> str:
        leading, old, trailing = m.group(1), m.group(2), m.group(3)
        total_w = len(leading) + len(old) + len(trailing)
        return format_hcorr(reverse_label(old, max_per), total_w)
    line = HCORRIDOR_RE.sub(repl_hcorr, line)

    # 3) 縦通路 / 階段ラベルセル (6 文字単位でスキャン)
    # 行末のラベルが走査漏れしないよう 6 の倍数までパディング
    padded = line + ' ' * ((6 - len(line) % 6) % 6)
    chars = list(padded)
    n = len(chars)
    for cs in range(0, n - 5, 6):
        cell = ''.join(chars[cs:cs + 6])
        m = CELL_LABEL_RE.match(cell)
        if m:
            old_label = m.group(2)
            new_label = reverse_label(old_label, max_per)
            new_cell = format_vert_cell(new_label)
            for i, ch in enumerate(new_cell):
                chars[cs + i] = ch
    return ''.join(chars).rstrip()


def main() -> None:
    ap = argparse.ArgumentParser(description="ダンジョン ASCII Art のラベル番号を逆順にする")
    ap.add_argument('input', help='入力ファイル (.txt)')
    ap.add_argument('-o', '--output', help='出力ファイル (省略時は標準出力)')
    args = ap.parse_args()

    text = Path(args.input).read_text(encoding='utf-8')
    max_per = find_max_per_prefix(text)
    if not max_per:
        sys.stderr.write("warning: R/P/S ラベルが見つかりませんでした\n")

    lines = text.split('\n')
    transformed = '\n'.join(transform_line(l, max_per) for l in lines)

    if args.output:
        Path(args.output).write_text(transformed, encoding='utf-8')
        sys.stderr.write(f"wrote {args.output}\n")
    else:
        sys.stdout.write(transformed)


if __name__ == '__main__':
    main()
