#!/usr/bin/env python3
"""
ダンジョン画像ビルダー

ASCII Art で書かれたダンジョンのトポロジを PNG 画像に変換する。
仕様: dungeon-image-builder-architecture.md

使い方:
    python3 tools/dungeon_image_builder.py path/to/topology.txt [-o out.png]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# --- スタイル定数 ---

CELL = 128
BUFFER_CELLS = 1
ROOM_INSET = 16
ROOM_BOX = CELL - 2 * ROOM_INSET
CORRIDOR_GAP = 32
GRID_STEP = CELL // 4
LINE_W = 2
GRID_LINE_W = 1
HEADING_LINE_GAP = 16

LABEL_FONT_SIZE = 16
STAIR_FONT_SIZE = 16
HEADING_FONT_SIZE = 16

GRID_DASH_PERIOD = 4
GRID_DASH_ON = 2

BG = (255, 255, 255)
FG = (0, 0, 0)
GRID_COLOR = (0xCC, 0xCC, 0xCC)

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    "/Library/Fonts/DejaVuSansMono.ttf",
    "DejaVuSansMono.ttf",
]


# --- ユーティリティ ---

def fail(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)
    sys.exit(1)


_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def get_font(size: int):
    if size in _font_cache:
        return _font_cache[size]
    for p in FONT_PATHS:
        try:
            f = ImageFont.truetype(p, size)
            _font_cache[size] = f
            return f
        except (OSError, IOError):
            continue
    fail("DejaVu Sans Mono フォントが見つかりません")


# --- パーサ ---

ROOM_BOX_RE = re.compile(r'\+[-+]{4}\+')
HEADING_RE = re.compile(r'===\s*(\S+)\s*===')
HCORRIDOR_RE = re.compile(r'-+([PH]\d{1,3})-+')
STAIR_RE = re.compile(r'([SE]\d{1,3})\s+([↓↑])\s*(\S+)')
STAIR_DANGLING_RE = re.compile(r'\b([SE]\d{1,3})\b')
ROOM_LABEL_RE = re.compile(r'^R\d{1,3}$')


P_LABEL_RE = re.compile(r'\b[PH]\d{1,3}\b')


def parse_topology(text: str):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        fail("入力が空です")

    non_empty = [l for l in lines if l.strip()]
    margin = min(len(l) - len(l.lstrip(' ')) for l in non_empty)
    lines = [l[margin:] if len(l) >= margin else '' for l in lines]

    cells = []
    headings = []

    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]

        m = HEADING_RE.search(line)
        if m:
            headings.append({'name': m.group(1), 'ascii_row': i})
            i += 1
            continue

        # 部屋ブロック (上端 / 中行 / 下端の 3 行)
        room_tops = list(ROOM_BOX_RE.finditer(line))
        if room_tops and i + 2 < n:
            mid = lines[i + 1]
            bot = lines[i + 2]
            valid_blocks = []
            valid = True
            for box in room_tops:
                bc = box.start()
                if not (bc + 5 < len(mid) and bc + 5 < len(bot)
                        and mid[bc] == '|' and mid[bc + 5] == '|'
                        and ROOM_BOX_RE.match(bot[bc:bc + 6])):
                    valid = False
                    break
                label = mid[bc + 1:bc + 5].strip()
                if not ROOM_LABEL_RE.match(label):
                    fail(f"部屋ラベル '{label}' が不正です: line {i + 2}")
                valid_blocks.append((bc, label))

            if valid and valid_blocks:
                for bc, label in valid_blocks:
                    cells.append({
                        'type': 'room',
                        'label': label,
                        'ascii_row': i + 1,
                        'ascii_col': bc,
                    })
                for cm in HCORRIDOR_RE.finditer(mid):
                    label = cm.group(1)
                    p_start = cm.start(1)
                    p_end = cm.end(1)
                    p_center = (p_start + p_end - 1) // 2
                    cell_col_chars = (p_center // 6) * 6
                    cells.append({
                        'type': 'corridor',
                        'orientation': 'horizontal',
                        'label': label,
                        'hidden': label.startswith('H'),
                        'ascii_row': i + 1,
                        'ascii_col': cell_col_chars,
                    })
                i += 3
                continue
            # 部屋ブロックとして妥当でない場合は後続の判定にフォールスルー

        # 縦通路 / 階段 (中行に複数ラベルがある可能性を考慮)
        if i + 2 < n:
            mid = lines[i + 1]
            bot = lines[i + 2]
            found = False

            for pm in P_LABEL_RE.finditer(mid):
                p_center = (pm.start() + pm.end() - 1) // 2
                if (p_center < len(line) and line[p_center] == '|'
                        and p_center < len(bot) and bot[p_center] == '|'):
                    label = pm.group(0)
                    cell_col_chars = (p_center // 6) * 6
                    cells.append({
                        'type': 'corridor',
                        'orientation': 'vertical',
                        'label': label,
                        'hidden': label.startswith('H'),
                        'ascii_row': i + 1,
                        'ascii_col': cell_col_chars,
                    })
                    found = True

            stair_labels_found = set()
            for sm in STAIR_RE.finditer(mid):
                s_center = (sm.start(1) + sm.end(1) - 1) // 2
                if (s_center < len(line) and line[s_center] == '|'
                        and s_center < len(bot) and bot[s_center] == '|'):
                    label = sm.group(1)
                    stair_labels_found.add(label)
                    cell_col_chars = (s_center // 6) * 6
                    cells.append({
                        'type': 'stair',
                        'label': label,
                        'hidden': label.startswith('E'),
                        'direction': sm.group(2),
                        'target_floor': sm.group(3),
                        'ascii_row': i + 1,
                        'ascii_col': cell_col_chars,
                    })
                    found = True

            for sm in STAIR_DANGLING_RE.finditer(mid):
                label = sm.group(1)
                if label in stair_labels_found:
                    continue
                s_center = (sm.start(1) + sm.end(1) - 1) // 2
                if (s_center < len(line) and line[s_center] == '|'
                        and s_center < len(bot) and bot[s_center] == '|'):
                    cell_col_chars = (s_center // 6) * 6
                    cells.append({
                        'type': 'stair',
                        'label': label,
                        'hidden': label.startswith('E'),
                        'ascii_row': i + 1,
                        'ascii_col': cell_col_chars,
                    })
                    found = True

            if found:
                i += 3
                continue

        i += 1

    if not cells:
        fail("セルが検出できませんでした")
    return cells, headings


def assign_grid(cells, headings) -> None:
    distinct_rows = sorted({c['ascii_row'] for c in cells})
    row_map = {r: idx for idx, r in enumerate(distinct_rows)}

    for c in cells:
        c['grid_row'] = row_map[c['ascii_row']]
        c['grid_col'] = c['ascii_col'] // 6

    # 見出しの描画位置: ASCII 上で最も近いセル行に配置
    # (見出しが先頭の場合は top buffer)
    for h in headings:
        h_line = h['ascii_row']
        prev_ascii = None
        next_ascii = None
        for r in distinct_rows:
            if r < h_line:
                prev_ascii = r
            elif r > h_line and next_ascii is None:
                next_ascii = r
                break

        if prev_ascii is None:
            h['draw_row'] = -1
        elif next_ascii is None:
            h['draw_row'] = row_map[prev_ascii]
        else:
            dist_prev = h_line - prev_ascii
            dist_next = next_ascii - h_line
            if dist_prev <= dist_next:
                h['draw_row'] = row_map[prev_ascii]
            else:
                h['draw_row'] = row_map[next_ascii]


# --- レンダラ ---

def cell_origin(grid_row: int, grid_col: int) -> tuple[int, int]:
    return (grid_col + BUFFER_CELLS) * CELL, (grid_row + BUFFER_CELLS) * CELL


def render(cells, headings, n_rows: int, n_cols: int, out_path: Path, nolabel: bool = False) -> None:
    img_w = (n_cols + 2 * BUFFER_CELLS) * CELL
    img_h = (n_rows + 2 * BUFFER_CELLS) * CELL
    img = Image.new('RGB', (img_w, img_h), BG)
    draw = ImageDraw.Draw(img)

    for x in range(0, img_w + 1, GRID_STEP):
        dotted_line(draw, (x, 0), (x, img_h), GRID_COLOR)
    for y in range(0, img_h + 1, GRID_STEP):
        dotted_line(draw, (0, y), (img_w, y), GRID_COLOR)

    cell_by_pos = {(c['grid_row'], c['grid_col']): c for c in cells}

    for cell in cells:
        if cell['type'] == 'room':
            draw_room(draw, cell, cell_by_pos, nolabel=nolabel)
        elif cell['type'] == 'corridor':
            draw_corridor(draw, cell, nolabel=nolabel)
        elif cell['type'] == 'stair':
            draw_stair(draw, cell, nolabel=nolabel)

    if not nolabel:
        for h in headings:
            draw_heading(draw, h)

    img.save(out_path)


def is_connector(cell) -> bool:
    if cell is None or cell['type'] not in ('corridor', 'stair'):
        return False
    if cell.get('hidden'):
        return False
    return True


def draw_room(draw: ImageDraw.ImageDraw, cell, cell_by_pos, nolabel: bool = False) -> None:
    x, y = cell_origin(cell['grid_row'], cell['grid_col'])
    rx0, ry0 = x + ROOM_INSET, y + ROOM_INSET
    rx1, ry1 = x + CELL - ROOM_INSET, y + CELL - ROOM_INSET
    cx, cy = x + CELL // 2, y + CELL // 2
    half = CORRIDOR_GAP // 2

    draw.rectangle([rx0, ry0, rx1, ry1], fill=BG)

    r, c = cell['grid_row'], cell['grid_col']
    conn = {
        'top': is_connector(cell_by_pos.get((r - 1, c))),
        'bottom': is_connector(cell_by_pos.get((r + 1, c))),
        'left': is_connector(cell_by_pos.get((r, c - 1))),
        'right': is_connector(cell_by_pos.get((r, c + 1))),
    }

    if conn['top']:
        draw.line([(rx0, ry0), (cx - half, ry0)], fill=FG, width=LINE_W)
        draw.line([(cx + half, ry0), (rx1, ry0)], fill=FG, width=LINE_W)
        draw.line([(cx - half, y), (cx - half, ry0)], fill=FG, width=LINE_W)
        draw.line([(cx + half, y), (cx + half, ry0)], fill=FG, width=LINE_W)
    else:
        draw.line([(rx0, ry0), (rx1, ry0)], fill=FG, width=LINE_W)

    if conn['bottom']:
        draw.line([(rx0, ry1), (cx - half, ry1)], fill=FG, width=LINE_W)
        draw.line([(cx + half, ry1), (rx1, ry1)], fill=FG, width=LINE_W)
        draw.line([(cx - half, ry1), (cx - half, y + CELL)], fill=FG, width=LINE_W)
        draw.line([(cx + half, ry1), (cx + half, y + CELL)], fill=FG, width=LINE_W)
    else:
        draw.line([(rx0, ry1), (rx1, ry1)], fill=FG, width=LINE_W)

    if conn['left']:
        draw.line([(rx0, ry0), (rx0, cy - half)], fill=FG, width=LINE_W)
        draw.line([(rx0, cy + half), (rx0, ry1)], fill=FG, width=LINE_W)
        draw.line([(x, cy - half), (rx0, cy - half)], fill=FG, width=LINE_W)
        draw.line([(x, cy + half), (rx0, cy + half)], fill=FG, width=LINE_W)
    else:
        draw.line([(rx0, ry0), (rx0, ry1)], fill=FG, width=LINE_W)

    if conn['right']:
        draw.line([(rx1, ry0), (rx1, cy - half)], fill=FG, width=LINE_W)
        draw.line([(rx1, cy + half), (rx1, ry1)], fill=FG, width=LINE_W)
        draw.line([(rx1, cy - half), (x + CELL, cy - half)], fill=FG, width=LINE_W)
        draw.line([(rx1, cy + half), (x + CELL, cy + half)], fill=FG, width=LINE_W)
    else:
        draw.line([(rx1, ry0), (rx1, ry1)], fill=FG, width=LINE_W)

    if not nolabel:
        label_centered(draw, cell['label'], cx, cy, LABEL_FONT_SIZE, with_bg=True)


def draw_corridor(draw: ImageDraw.ImageDraw, cell, nolabel: bool = False) -> None:
    x, y = cell_origin(cell['grid_row'], cell['grid_col'])
    cx, cy = x + CELL // 2, y + CELL // 2
    half = CORRIDOR_GAP // 2
    hidden = cell.get('hidden', False)
    inset = ROOM_INSET if hidden else 0
    if cell['orientation'] == 'horizontal':
        l1y, l2y = cy - half, cy + half
        x0, x1 = x + inset, x + CELL - inset
        draw.line([(x0, l1y), (x1, l1y)], fill=FG, width=LINE_W)
        draw.line([(x0, l2y), (x1, l2y)], fill=FG, width=LINE_W)
    else:
        l1x, l2x = cx - half, cx + half
        y0, y1 = y + inset, y + CELL - inset
        draw.line([(l1x, y0), (l1x, y1)], fill=FG, width=LINE_W)
        draw.line([(l2x, y0), (l2x, y1)], fill=FG, width=LINE_W)
    if not nolabel:
        label_centered(draw, cell['label'], cx, cy, LABEL_FONT_SIZE, with_bg=True)


def draw_stair(draw: ImageDraw.ImageDraw, cell, nolabel: bool = False) -> None:
    x, y = cell_origin(cell['grid_row'], cell['grid_col'])
    cx, cy = x + CELL // 2, y + CELL // 2
    half = CORRIDOR_GAP // 2
    l1x, l2x = cx - half, cx + half
    hidden = cell.get('hidden', False)
    inset = ROOM_INSET if hidden else 0
    y0, y1 = y + inset, y + CELL - inset

    draw.rectangle([l1x, y0, l2x, y1], fill=BG)

    draw.line([(l1x, y0), (l1x, y1)], fill=FG, width=LINE_W)
    draw.line([(l2x, y0), (l2x, y1)], fill=FG, width=LINE_W)

    span = y1 - y0
    for k in range(1, 6):
        sy = y0 + (span * k) // 6
        draw.line([(l1x, sy), (l2x, sy)], fill=FG, width=LINE_W)

    if not nolabel:
        label_centered(draw, cell['label'], cx, cy, STAIR_FONT_SIZE, with_bg=True)


def draw_heading(draw: ImageDraw.ImageDraw, h) -> None:
    draw_row = h['draw_row']
    x = 0
    y = (draw_row + BUFFER_CELLS) * CELL
    cx, cy = x + CELL // 2, y + CELL // 2

    line1_y = cy - HEADING_LINE_GAP // 2
    line2_y = cy + HEADING_LINE_GAP // 2
    draw.line([(x, line1_y), (x + CELL, line1_y)], fill=FG, width=LINE_W)
    draw.line([(x, line2_y), (x + CELL, line2_y)], fill=FG, width=LINE_W)

    label_centered(draw, h['name'], cx, cy, HEADING_FONT_SIZE, with_bg=True)


def dotted_line(draw: ImageDraw.ImageDraw, p1, p2, fill) -> None:
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        y_start = min(y1, y2)
        y_end = max(y1, y2)
        for y in range(y_start, y_end + 1):
            if (y - y_start) % GRID_DASH_PERIOD < GRID_DASH_ON:
                draw.point((x1, y), fill=fill)
    elif y1 == y2:
        x_start = min(x1, x2)
        x_end = max(x1, x2)
        for x in range(x_start, x_end + 1):
            if (x - x_start) % GRID_DASH_PERIOD < GRID_DASH_ON:
                draw.point((x, y1), fill=fill)


def label_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int,
    cy: int,
    size: int,
    with_bg: bool = False,
) -> None:
    font = get_font(size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    tx = cx - text_w // 2 - bbox[0]
    ty = cy - text_h // 2 - bbox[1]
    if with_bg:
        pad = 1
        bg_box = (
            cx - text_w // 2 - pad,
            cy - text_h // 2 - pad,
            cx + text_w // 2 + pad,
            cy + text_h // 2 + pad,
        )
        draw.rectangle(bg_box, fill=BG)
    draw.text((tx, ty), text, font=font, fill=FG)


# --- メイン ---

def main() -> None:
    ap = argparse.ArgumentParser(description="ダンジョントポロジを PNG 画像に変換")
    ap.add_argument('input', help='入力トポロジファイル (.txt)')
    ap.add_argument('-o', '--output', help='出力 PNG パス (デフォルト: <input>.png)')
    ap.add_argument('--nolabel', action='store_true',
                    help='ラベル (Rn/Pn/Sn/Hn/En) とフロア見出しを描画しない')
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        fail(f"入力ファイルが見つかりません: {in_path}")
    text = in_path.read_text(encoding='utf-8')

    cells, headings = parse_topology(text)
    assign_grid(cells, headings)
    n_cols = max(c['grid_col'] for c in cells) + 1
    n_rows = max(c['grid_row'] for c in cells) + 1

    out_path = Path(args.output) if args.output else in_path.with_suffix('.png')
    render(cells, headings, n_rows, n_cols, out_path, nolabel=args.nolabel)
    print(f"wrote {out_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
