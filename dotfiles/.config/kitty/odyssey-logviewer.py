#!/usr/bin/python3
"""Bounded, resize-safe socklog viewer. GPL-3.0-or-later."""
import argparse
import curses
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

_spec = importlib.util.spec_from_file_location('odyssey_terminal_ui', Path(__file__).with_name('odyssey_terminal.py'))
ui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ui)
MAX_BYTES = 2 * 1024 * 1024
MAX_LINES = 10000


def channels(root):
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def read_tail(path, previous=None):
    """Track rotation/truncation, and bound memory even for huge log files."""
    try:
        stat = path.stat()
        signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        if signature == previous:
            return None, previous, ''
        with path.open('rb') as stream:
            offset = max(0, stat.st_size - MAX_BYTES)
            stream.seek(offset)
            data = stream.read(MAX_BYTES)
        if offset:
            data = data.partition(b'\n')[2]
        rows = data.decode('utf-8', 'replace').splitlines()
        truncated = bool(offset or len(rows) > MAX_LINES)
        return rows[-MAX_LINES:], signature, 'Recent tail only · 2 MiB / 10,000 lines' if truncated else ''
    except PermissionError:
        return ['Access denied. Close and reopen System logs to request elevated access.'], None, 'Access denied'
    except OSError as error:
        return [str(error)], None, 'Log unavailable'


def channel_view(names, selected, width):
    """Keep the selected channel visible; clip a single long name if needed."""
    if not names or width < 1:
        return []
    widths = [min(width, ui.width(name) + 2) for name in names]
    first = selected
    used = widths[selected]
    while first > 0 and used + widths[first - 1] <= width:
        first -= 1
        used += widths[first]
    result = []
    x = 0
    for index in range(first, len(names)):
        size = min(widths[index], width - x)
        if size <= 0:
            break
        result.append((index, x, ui.fit(' ' + names[index] + ' ', size)))
        x += size
    return result


def colors():
    if not curses.has_colors():
        return (0, curses.A_REVERSE, curses.A_BOLD, curses.A_DIM)
    curses.start_color()
    curses.use_default_colors()
    # Fixed xterm colors: do not alter the user's terminal palette.
    if curses.COLORS >= 256:
        pairs = ((232, 188), (255, 234), (196, 188), (244, -1))
    else:
        pairs = ((curses.COLOR_BLACK, curses.COLOR_WHITE),
                 (curses.COLOR_WHITE, curses.COLOR_BLACK),
                 (curses.COLOR_RED, curses.COLOR_WHITE), (curses.COLOR_WHITE, -1))
    for index, (fg, bg) in enumerate(pairs, 1):
        curses.init_pair(index, fg, bg)
    return tuple(curses.color_pair(i) for i in range(1, 5))


def view(screen, root):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    normal, selected_attr, accent, dim = colors()
    screen.keypad(True)
    screen.timeout(500)
    try:
        names = channels(root)
    except OSError as error:
        names, error_text = [], str(error)
    else:
        error_text = 'No socklog channels found at ' + str(root)
    selected = offset = 0
    live = True
    rows = []
    signature = None
    note = ''
    help_open = False

    def put(y, x, text, attr=0, width=None):
        height, columns = screen.getmaxyx()
        if 0 <= y < height and 0 <= x < columns - 1:
            try:
                screen.addstr(y, x, ui.clip(text, min(width or columns, columns - x - 1)), attr)
            except curses.error:
                pass

    while True:
        height, columns = screen.getmaxyx()
        visible = max(1, height - 5)
        if names:
            loaded, new_signature, new_note = read_tail(root / names[selected] / 'current', signature)
            if loaded is not None:
                rows, signature, note = loaded, new_signature, new_note
        maximum = max(0, len(rows) - visible)
        offset = maximum if live else min(offset, maximum)
        screen.erase()
        put(0, 0, ' ' * columns, normal)
        put(0, 0, ' LOGS', normal | curses.A_BOLD)
        mode = 'LIVE' if live else 'PAUSED'
        put(0, max(6, columns - len(mode) - 2), mode, accent if live else normal)
        if not names:
            put(2, 1, error_text)
            put(4, 1, 'Enable the socklog service to browse system logs.', dim)
        else:
            for index, x, label in channel_view(names, selected, columns - 1):
                put(1, x, label, selected_attr | curses.A_BOLD if index == selected else normal)
            if help_open:
                hints = ['KEYBOARD', '', 'Left / Right  Change channel', 'Up / Down     Pause and scroll',
                         'Page Up/Down  Scroll a page', 'g / G         First / last buffered line',
                         'Space or t    Toggle live follow', 'r             Rescan channels / refresh',
                         '?             Show / hide this help', 'q or Esc      Close']
                for index, line in enumerate(hints[:visible]):
                    put(3 + index, 1, line)
            else:
                for index, line in enumerate(rows[offset:offset + visible]):
                    put(3 + index, 0, line)
            position = f'{names[selected]} · {offset+1 if rows else 0}–{min(offset+visible, len(rows))}/{len(rows)}'
            put(height - 2, 0, position + (' · ' + note if note else ''), dim)
        put(height - 1, 0, '←→ Channel   Space Live   ? Help   q Close', dim)
        screen.refresh()
        key = screen.getch()
        if key in (ord('q'), 27):
            if help_open:
                help_open = False
            else:
                return
        elif key == ord('?'):
            help_open = not help_open
        elif key in (curses.KEY_RIGHT, curses.KEY_LEFT) and names:
            selected = (selected + (1 if key == curses.KEY_RIGHT else -1)) % len(names)
            signature = None
            offset = 0
        elif key in (ord(' '), ord('t')):
            live = not live
        elif key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE, ord('g'), ord('G')):
            live = False
            if key == ord('g'):
                offset = 0
            elif key == ord('G'):
                offset = maximum
            else:
                delta = {curses.KEY_UP: -1, curses.KEY_DOWN: 1,
                         curses.KEY_PPAGE: -visible, curses.KEY_NPAGE: visible}[key]
                offset = max(0, min(maximum, offset + delta))
        elif key == ord('r'):
            old = names[selected] if names else None
            try:
                names = channels(root)
                selected = names.index(old) if old in names else 0
            except OSError as error:
                names, error_text = [], str(error)
            signature = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-dir', type=Path, default=Path('/var/log/socklog'))
    parser.add_argument('--offer-elevation', action='store_true')
    args = parser.parse_args()
    root = args.log_dir.expanduser().resolve()
    denied = False
    try:
        names = channels(root)
        denied = any((root / name / 'current').exists() and
                     not os.access(root / name / 'current', os.R_OK) for name in names)
    except PermissionError:
        denied = True
    except OSError:
        pass
    if denied and args.offer_elevation and os.geteuid() != 0:
        command = shutil.which('sudo') or shutil.which('doas')
        if command:
            print('Some socklog channels need elevated read access.')
            answer = input('Open the log viewer with ' + Path(command).name + '? [y/N] ')
            if answer.strip().lower() in ('y', 'yes'):
                return subprocess.call([command, sys.executable, str(Path(__file__).resolve()), '--log-dir', str(root)])
    curses.wrapper(view, root)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
