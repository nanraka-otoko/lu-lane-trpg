#!/usr/bin/env python3
"""
ダンジョンビルダー

簡略表記のマップを `dungeon_image_builder.py` でパース可能な ASCII Art に変換する。
仕様: dungeon-builder-architecture.md

入力例:
    2F
      R
      s
    R-R
      |
    R-R
    | |
    R-R

記号:
    R   部屋
    -   横通路
    |   縦通路
    s   階段 (下方向)
    h   隠し通路 (向きは隣接セルから推論)
    e   隠し階段 (下方向)

部屋・通路・階段・隠し通路・隠し階段は出現順に
R1, R2, ..., P1, P2, ..., S1, S2, ..., H1, H2, ..., E1, E2, ... と採番する。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# --- ユーティリティ ---

def fail(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)
    sys.exit(1)


def next_floor(current: str) -> str:
    """次の (一段下の) フロア名を返す。

    2F → 1F → B1F → B2F → ...
    """
    if current.startswith('B'):
        n = int(current[1:-1])
        return f"B{n + 1}F"
    n = int(current[:-1])
    if n == 1:
        return "B1F"
    return f"{n - 1}F"


# --- パーサ ---

def parse_input(text: str):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        fail("入力が空です")

    top_floor = lines[0].strip()
    if not top_floor:
        fail("先頭行にフロア名がありません")
    grid = lines[1:]
    return top_floor, grid


def detect_h_orientation(grid, r, c):
    """隠し通路 'h' の向きを隣接セルから推論する。"""
    horizontal = cell_at(grid, r, c - 1) == 'R' or cell_at(grid, r, c + 1) == 'R'
    vertical = cell_at(grid, r - 1, c) == 'R' or cell_at(grid, r + 1, c) == 'R'
    if horizontal and not vertical:
        return 'horizontal'
    if vertical and not horizontal:
        return 'vertical'
    # 両隣接 or 不明 → デフォルトは水平
    return 'horizontal'


def number_cells(grid):
    """グリッドを上から下、左から右に走査してラベルを採番する。"""
    rooms = []
    corridors = []
    stairs = []
    rc = pc = hc = sc = ec = 0

    for r, line in enumerate(grid):
        for c, ch in enumerate(line):
            if ch == 'R':
                rc += 1
                rooms.append({'row': r, 'col': c, 'label': f'R{rc}'})
            elif ch == '-':
                pc += 1
                corridors.append({'row': r, 'col': c, 'label': f'P{pc}', 'orientation': 'horizontal'})
            elif ch == '|':
                pc += 1
                corridors.append({'row': r, 'col': c, 'label': f'P{pc}', 'orientation': 'vertical'})
            elif ch == 'h':
                hc += 1
                orientation = detect_h_orientation(grid, r, c)
                corridors.append({'row': r, 'col': c, 'label': f'H{hc}', 'orientation': orientation})
            elif ch == 's':
                sc += 1
                dangling = cell_at(grid, r - 1, c) != 'R' or cell_at(grid, r + 1, c) != 'R'
                stairs.append({'row': r, 'col': c, 'label': f'S{sc}', 'dangling': dangling})
            elif ch == 'e':
                ec += 1
                dangling = cell_at(grid, r - 1, c) != 'R' or cell_at(grid, r + 1, c) != 'R'
                stairs.append({'row': r, 'col': c, 'label': f'E{ec}', 'dangling': dangling})
            elif ch in (' ', '\t'):
                pass
            else:
                fail(f"未知の文字 '{ch}' (row={r}, col={c})")

    return rooms, corridors, stairs


def _has_floor_changing_stair(grid, r):
    """行 r にフロア遷移を引き起こす階段 (両端に部屋がある) があるか。

    片端のみ部屋に接続する階段 (外部接続) はフロア遷移を起こさない。
    """
    if r < 0 or r >= len(grid):
        return False
    for c, ch in enumerate(grid[r]):
        if ch in ('s', 'e'):
            if cell_at(grid, r - 1, c) == 'R' and cell_at(grid, r + 1, c) == 'R':
                return True
    return False


def assign_floors(grid, top_floor):
    """各行が属するフロア名を返す。

    行 N の手前に両端接続の階段 (s または e) があれば、N は次のフロアに属する。
    片端のみの階段 (外部接続) ではフロアを進めない。
    """
    floors = []
    current = top_floor
    for r in range(len(grid)):
        if r > 0 and _has_floor_changing_stair(grid, r - 1):
            current = next_floor(current)
        floors.append(current)
    return floors


# --- レンダラ ---

def cell_at(grid, r, c):
    if 0 <= r < len(grid) and 0 <= c < len(grid[r]):
        return grid[r][c]
    return ' '


def render_room_box(grid, r, c, label):
    top_port = cell_at(grid, r - 1, c) in ('|', 's')
    bot_port = cell_at(grid, r + 1, c) in ('|', 's')
    top = '+-+--+' if top_port else '+----+'
    bot = '+-+--+' if bot_port else '+----+'

    if len(label) == 2:
        mid = f'| {label} |'
    elif len(label) == 3:
        mid = f'|{label} |'
    elif len(label) == 4:
        mid = f'|{label}|'
    else:
        fail(f"部屋ラベルが長すぎます: {label}")
    return (top, mid, bot)


def render_horizontal_corridor(label):
    if len(label) == 2:
        mid = f'--{label}--'
    elif len(label) == 3:
        mid = f'-{label}--'
    elif len(label) == 4:
        mid = f'-{label}-'
    else:
        fail(f"通路ラベルが長すぎます: {label}")
    return ('      ', mid, '      ')


def render_vertical_corridor(label):
    top = '  |   '
    bot = '  |   '
    if len(label) == 2:
        mid = f'  {label}  '
    elif len(label) == 3:
        mid = f' {label}  '
    elif len(label) == 4:
        mid = f' {label} '
    else:
        fail(f"通路ラベルが長すぎます: {label}")
    return (top, mid, bot)


def render_stair_label_chunk(label):
    if len(label) == 2:
        return f'  {label}  '
    if len(label) == 3:
        return f' {label}  '
    if len(label) == 4:
        return f' {label} '
    fail(f"階段ラベルが長すぎます: {label}")


def write_buf(buf, pos, s):
    while len(buf) < pos + len(s):
        buf.append(' ')
    for i, ch in enumerate(s):
        buf[pos + i] = ch


def render_grid(grid, rooms, corridors, stairs, floors, top_floor):
    cell_lookup = {}
    for room in rooms:
        cell_lookup[(room['row'], room['col'])] = ('room', room['label'])
    for corr in corridors:
        cell_lookup[(corr['row'], corr['col'])] = ('corridor', corr['label'], corr['orientation'])
    for s in stairs:
        cell_lookup[(s['row'], s['col'])] = ('stair', s['label'], s.get('dangling', False))

    n_rows = len(grid)
    n_cols = max((len(line) for line in grid), default=0)

    output = []
    output.append(f'=== {top_floor} ===')
    output.append('')

    for r in range(n_rows):
        top_buf = [' '] * (6 * n_cols)
        mid_buf = [' '] * (6 * n_cols)
        bot_buf = [' '] * (6 * n_cols)
        stair_continuations = []

        for c in range(n_cols):
            entry = cell_lookup.get((r, c))
            if entry is None:
                continue

            if entry[0] == 'room':
                _, label = entry
                t, m, b = render_room_box(grid, r, c, label)
                write_buf(top_buf, 6 * c, t)
                write_buf(mid_buf, 6 * c, m)
                write_buf(bot_buf, 6 * c, b)
            elif entry[0] == 'corridor':
                _, label, orientation = entry
                if orientation == 'horizontal':
                    t, m, b = render_horizontal_corridor(label)
                else:
                    t, m, b = render_vertical_corridor(label)
                write_buf(top_buf, 6 * c, t)
                write_buf(mid_buf, 6 * c, m)
                write_buf(bot_buf, 6 * c, b)
            elif entry[0] == 'stair':
                _, label, dangling = entry
                write_buf(top_buf, 6 * c, '  |   ')
                write_buf(mid_buf, 6 * c, render_stair_label_chunk(label))
                write_buf(bot_buf, 6 * c, '  |   ')
                if not dangling:
                    target = next_floor(floors[r])
                    stair_continuations.append((6 * c + 6, f'↓ {target}'))

        for pos, cont in stair_continuations:
            write_buf(mid_buf, pos, cont)

        output.append(''.join(top_buf).rstrip())
        output.append(''.join(mid_buf).rstrip())
        output.append(''.join(bot_buf).rstrip())

        row_stairs = [s for s in stairs if s['row'] == r]
        non_dangling = [s for s in row_stairs if not s.get('dangling')]
        if non_dangling:
            new_floor = next_floor(floors[r])
            output.append(f'=== {new_floor} ===')
            connector_buf = []
            for s in sorted(non_dangling, key=lambda x: x['col']):
                write_buf(connector_buf, 6 * s['col'] + 2, '|')
            output.append(''.join(connector_buf).rstrip())

    return '\n'.join(output) + '\n'


# --- メイン ---

def main():
    ap = argparse.ArgumentParser(description="簡略マップから dungeon_image_builder 互換の ASCII Art を生成")
    ap.add_argument('input', help='入力ファイル (.txt)')
    ap.add_argument('-o', '--output', help='出力ファイル (省略時は標準出力)')
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        fail(f"入力ファイルが見つかりません: {in_path}")
    text = in_path.read_text(encoding='utf-8')

    top_floor, grid = parse_input(text)
    rooms, corridors, stairs = number_cells(grid)
    floors = assign_floors(grid, top_floor)

    output = render_grid(grid, rooms, corridors, stairs, floors, top_floor)

    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(output)


if __name__ == '__main__':
    main()
