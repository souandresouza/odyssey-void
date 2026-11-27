"""Shared Odyssey Terminal presentation and action definitions. GPL-3.0-or-later."""
import os
import json
from pathlib import Path
import re
import shutil
import unicodedata

PALETTE = {
    'surface': '#d5d3d0', 'raised': '#e3e0dc', 'selected': '#191918',
    'text': '#191918', 'secondary': '#494641', 'muted': '#5b554e',
    'border': '#b4b0aa', 'paper': '#f2f1ef', 'red': '#e8192c',
    'terminal': '#191918', 'terminal_text': '#e3e0dc',
    'launch_bg': '#191918', 'launch_fg': '#e3e0dc',
    'launch_input': '#2b2926', 'launch_muted': '#aaa39a',
    'launch_secondary': '#d5d3d0', 'launch_selection': '#e3e0dc',
}


def clean(text):
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(text))
    return ''.join(c for c in text if not unicodedata.category(c).startswith('C'))


def width(text):
    try:
        from kitty.fast_data_types import wcswidth
        return max(0, wcswidth(text))
    except ImportError:
        return sum(0 if unicodedata.combining(c) else
                   2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1
                   for c in text)


def clip(text, limit, ellipsis=True):
    text = clean(text)
    limit = max(0, int(limit))
    if width(text) <= limit:
        return text
    suffix = '…' if ellipsis and limit else ''
    out = ''
    for char in text:
        if width(out + char) > limit - width(suffix):
            break
        out += char
    return out + suffix


def fit(text, limit):
    text = clip(text, limit)
    return text + ' ' * max(0, limit - width(text))


def compact_title(title):
    title = clean(title).strip()
    match = re.match(r'^\[([^ ]+) (.*)\][#$]$', title)
    if match:
        host, path = match.groups()
        tail = path.rstrip('/').rsplit('/', 1)[-1] or '/'
        return f'{tail} · {host}'
    return title or 'Terminal'


def color(name, background=False):
    value = PALETTE.get(name, name).lstrip('#')
    rgb = tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    return '\x1b[%s;2;%s;%s;%sm' % (48 if background else 38, *rgb)


def actions(config_dir, which=shutil.which):
    """Commands are argv lists. Missing optional tools remain visible."""
    config_dir = Path(config_dir)
    entries = []
    try:
        state = json.loads((config_dir / '.odyssey-local-state.json').read_text())
    except (OSError, ValueError):
        state = {}
    preview = state.get('mode') == 'preview'

    def add(id_, group, title, description, kind, argv=(), missing=''):
        entries.append(dict(id=id_, group=group, title=title, description=description,
                            kind=kind, argv=list(argv), missing=missing))

    add('newtab', 'Terminal', 'New tab', 'Open a shell in the current directory.', 'newtab')
    add('newwindow', 'Terminal', 'New window', 'Open a separate terminal window in the current directory.', 'newwindow')
    add('vsplit', 'Terminal', 'Split side by side', 'Add a pane to the right of the current pane.', 'vsplit')
    add('hsplit', 'Terminal', 'Split above / below', 'Add a pane below the current pane.', 'hsplit')
    add('zoom', 'Terminal', 'Focus this pane', 'Toggle between the current layout and a single visible pane.', 'zoom')
    add('rename', 'Terminal', 'Rename tab', 'Set a tab name, or clear it to restore its automatic title.', 'rename')

    def tool(id_, group, title, desc, candidates, kind='tool'):
        for argv in candidates:
            if which(argv[0]):
                add(id_, group, title, desc, kind, argv)
                return
        add(id_, group, title, desc, kind, (), 'Requires ' + ' or '.join(a[0] for a in candidates) + '.')

    tool('processes', 'System', 'Process monitor', 'Inspect CPU, memory and running processes.', [('btop',), ('htop',), ('top',)])
    tool('disk', 'System', 'Disk usage', 'Refresh filesystem capacity every two seconds.', [('watch', '-n', '2', 'df', '-h')])
    tool('network', 'System', 'Network activity', 'Inspect traffic on network interfaces.', [('bmon',), ('nload',), ('watch', '-n', '2', 'ip', '-s', 'link')])
    py = which('python3')
    log = config_dir / 'odyssey-logviewer.py'
    add('logs', 'System', 'System logs', 'Browse socklog channels. Request elevated access only when needed.',
        'logs', (py or 'python3', str(log)), '' if py and log.is_file() else 'Requires Python 3 and the log viewer.')
    tool('files', 'Tools', 'File manager', 'Browse files in the current directory.', [('yazi',), ('ranger',), ('nnn',), ('mc',)])
    tool('editor', 'Tools', 'Text editor', 'Open a terminal editor.', [('nano',), ('micro',), ('vim',), ('vi',)])
    plan9 = '/usr/lib/plan9/bin/9'
    for name in ('rc', 'acme', 'sam'):
        installed = os.access(plan9, os.X_OK) and os.access('/usr/lib/plan9/bin/' + name, os.X_OK)
        add('p9_' + name, 'Plan 9', 'rc shell' if name == 'rc' else name.capitalize(),
            'Open the Plan 9 shell in a tab.' if name == 'rc' else 'Open the Plan 9 editor in its own window.',
            'tool' if name == 'rc' else 'external', (plan9, name),
            '' if installed else 'Requires plan9port (' + name + ').')
    preferences = which('odyssey-terminal-preferences') or which('terminal-preferences')
    add('preferences', 'Settings', 'Preferences', 'Open your existing terminal preferences application.',
        'external', (preferences,) if preferences else (),
        'Available after installation; this preview uses isolated files.' if preview else
        '' if preferences else 'Terminal preferences application not found.')
    add('config', 'Settings', 'Edit user settings', 'Edit user.conf. Your overrides are loaded after the Odyssey theme.', 'config')
    add('shortcuts', 'Settings', 'Keyboard shortcuts', 'View navigation keys and your custom shortcut file.', 'help')
    add('restore', 'Settings', 'Restore previous configuration', 'Restore the snapshot made before applying this local revision.',
        'restore', missing='Close the preview window to discard it.' if preview else
        '' if state.get('backup') else 'No local revision snapshot found.')
    add('vanilla', 'Settings', 'Open plain Kitty', 'Open a separate window using Kitty defaults. Your files stay in place.', 'vanilla')
    return entries


def filtered(entries, query):
    words = query.casefold().split()
    return [e for e in entries if all(word in (' '.join((e['group'], e['title'], e['description']))).casefold() for word in words)]


def launcher_layout(entries, cols, rows, index=0, start=0):
    """Use available rows; group complete sections into two columns when wide.

    Compact rows are the fallback when section headings would hide actions.
    Returned rectangles also define the clickable area, avoiding a second
    layout calculation in the mouse handler.
    """
    width = min(112, cols - 4)
    x = max(1, (cols - width) // 2)
    capacity = max(1, rows - 9)
    columns = 2 if width >= 90 and len(entries) > 10 else 1
    gap = 4 if columns == 2 else 0
    cell_width = (width - gap) // columns
    groups = []
    for number, entry in enumerate(entries):
        if not groups or groups[-1][0] != entry['group']:
            groups.append((entry['group'], []))
        groups[-1][1].append(number)

    def height(parts):
        return sum(1 + len(indices) for _, indices in parts) + max(0, len(parts) - 1)

    parts = [groups]
    if columns == 2 and len(groups) > 1:
        cut = min(range(1, len(groups)),
                  key=lambda n: (max(height(groups[:n]), height(groups[n:])),
                                 abs(height(groups[:n]) - height(groups[n:]))))
        parts = [groups[:cut], groups[cut:]]
    grouped = bool(groups) and len(parts) == columns and max(map(height, parts)) <= capacity
    cells, headings = [], []
    if grouped:
        body_rows = max(map(height, parts))
        start, visible = 0, len(entries)
        for col, section in enumerate(parts):
            row = 0
            for group, indices in section:
                headings.append((col, row, group))
                row += 1
                for number in indices:
                    cells.append((col, row, number))
                    row += 1
                row += 1
    else:
        body_rows = max(1, min(capacity, (len(entries) + columns - 1) // columns))
        visible = columns * body_rows
        start = max(0, min(start, index, max(0, len(entries) - visible)))
        if index >= start + visible:
            start = index - visible + 1
        for offset, number in enumerate(range(start, min(len(entries), start + visible))):
            col, row = divmod(offset, body_rows)
            cells.append((col, row, number))
    y = max(0, (rows - body_rows - 9) // 2)
    return dict(x=x, y=y, width=width, columns=columns, start=start,
                visible_count=visible, grouped=grouped, body_rows=body_rows,
                detail_y=y + body_rows + 6, footer_y=y + body_rows + 8,
                cells=[(x + col * (cell_width + gap), y + 5 + row, cell_width, number)
                       for col, row, number in cells],
                headings=[(x + col * (cell_width + gap), y + 5 + row, cell_width, group)
                          for col, row, group in headings])


def tab_buttons(budget):
    if budget >= 18:
        return [('launch', ' Launch '), ('newtab', ' + ')]
    if budget >= 12:
        return [('launch', ' > '), ('newtab', ' + ')]
    if budget >= 9:
        return [('launch', ' > ')]
    return []


def tab_strip_layout(columns, count, active=0, start=0):
    """Fixed navigation controls and a readable slice containing the active tab."""
    if columns >= 40:
        buttons = [('launch', ' Launch '), ('newtab', ' + '),
                   ('previous', ' ‹ '), ('next', ' › ')]
    elif columns >= 20:
        buttons = [('launch', ' > '), ('newtab', ' + '),
                   ('previous', ' ‹ '), ('next', ' › ')]
    else:
        buttons = [('launch', '>'), ('newtab', '+'),
                   ('previous', '‹'), ('next', '›')][:max(0, columns - 1)]
    active = max(0, min(active, count - 1))
    counter = f' {active + 1:>{len(str(count))}}/{count} ' if count > 1 and columns >= 24 else ''
    left = sum(len(label) for _, label in buttons) + 1
    available = max(0, columns - left - len(counter) - 1)
    capacity = max(1, available // 16)
    start = max(0, min(start, active, max(0, count - capacity)))
    if active >= start + capacity:
        start = active - capacity + 1
    visible = min(count, capacity)
    width = min(28, available // max(1, visible))
    tabs = [(number, left + offset * width, width)
            for offset, number in enumerate(range(start, min(count, start + visible)))] if width >= 2 else []
    return dict(buttons=buttons, tabs=tabs, start=start, counter=counter,
                counter_x=columns - len(counter), active=active)
