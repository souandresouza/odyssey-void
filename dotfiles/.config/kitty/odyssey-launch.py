#!/usr/bin/python3
"""Odyssey Terminal launcher for Kitty 0.46.2/0.48.2. GPL-3.0-or-later."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

from kittens.tui.handler import Handler
from kittens.tui.loop import EventType, Loop, MouseButton
from kittens.tui.operations import MouseTracking
from kitty.constants import config_dir

CONFIG = Path(config_dir)
_spec = importlib.util.spec_from_file_location('odyssey_terminal_ui', CONFIG / 'odyssey_terminal.py')
ui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ui)


class LaunchMenu(Handler):
    mouse_tracking = MouseTracking.full

    def __init__(self):
        self.entries = ui.actions(CONFIG)
        self.query = ''
        self.index = self.start = 0
        self.selected = None
        self.help = False
        self.help_offset = 0
        self.hits = []
        self.pressed = None
        self.mouse_position = None
        self.visible_count = 1

    def initialize(self):
        self.write('\x1b[?25l')
        self.draw()

    def finalize(self):
        self.write('\x1b[0m\x1b[?25h')

    def on_resize(self, size):
        super().on_resize(size)
        self.pressed = None
        self.mouse_position = None
        self.draw()

    def help_lines(self):
        lines = [
            'LAUNCHER', '',
            'Type to search       Filter all actions',
            'Up / Down, Tab       Select the next / previous action',
            'Left / Right        Move between columns',
            'Mouse wheel         Select one action per step',
            'Click or Enter      Open an action',
            'Page Up / Down       Scroll a page',
            'Ctrl+U               Clear the search',
            'Esc                  Return to your terminal',
            '', 'TERMINAL DEFAULTS', '',
            'Ctrl+Shift+Space     Open this launcher',
            'Ctrl+Shift+T         New tab in the current directory',
            'Ctrl+Shift+Enter     New pane in the current directory',
            'Ctrl+Shift+N         New OS window',
            'Ctrl+Shift+W         Close the current tab',
            'Click the tab ×      Close that tab',
            'Tab bar ‹ / ›        Previous / next tab',
            'Ctrl+Shift+Left/Right Previous / next tab',
            '', 'Your own mappings take precedence.',
        ]
        try:
            custom = (CONFIG / 'keybindings.conf').read_text()
        except OSError:
            custom = ''
        maps = [ui.clean(line.strip()) for line in custom.splitlines()
                if line.strip().startswith(('map ', 'mouse_map '))]
        if maps:
            lines += ['', 'YOUR KEYBINDINGS', ''] + maps
        return lines

    def draw(self):
        cols, rows = self.screen_size.cols, self.screen_size.rows
        self.hits = []
        bg, fg = ui.color('launch_bg', True), ui.color('launch_fg')
        out = [bg, fg, '\x1b[2J\x1b[H']

        def put(y, x, text, width, foreground='launch_fg', background='launch_bg', bold=False):
            if not (0 <= y < rows and 0 <= x < cols):
                return
            # Leave the last physical column empty to avoid autowrap.
            width = min(width, cols - x - 1)
            if width <= 0:
                return
            out.extend((f'\x1b[{y+1};{x+1}H', '\x1b[1m' if bold else '\x1b[22m',
                        ui.color(foreground), ui.color(background, True), ui.fit(text, width)))

        if cols < 24 or rows < 10:
            put(0, 0, 'Terminal · Launch', cols)
            put(2, 0, 'Enlarge this window.', cols)
            put(rows - 1, 0, 'Esc  Close', cols)
            self.write(''.join(out))
            return
        entries = ui.filtered(self.entries, self.query)
        self.index = max(0, min(self.index, len(entries) - 1))
        layout = ui.launcher_layout(entries, cols, rows, self.index, self.start)
        width, x, y = layout['width'], layout['x'], layout['y']
        if self.help:
            y = 1 if rows >= 16 else 0
        put(y, x, 'TERMINAL', width, 'launch_muted')
        put(y + 1, x, 'Keyboard shortcuts' if self.help else 'Launch', width, bold=True)
        if self.help:
            lines = self.help_lines()
            count = max(1, rows - y - 6)
            self.visible_count = count
            self.help_offset = max(0, min(self.help_offset, len(lines) - count))
            for row, line in enumerate(lines[self.help_offset:self.help_offset + count]):
                put(y + 3 + row, x, line, width, 'launch_secondary')
            put(rows - 2, x, '↑↓ / Wheel  Scroll   Esc  Back', width, 'launch_muted')
        else:
            query = ui.clip(self.query, width - 13)
            put(y + 3, x, ' Search  ' + query + ('_' if not query else ''), width,
                'launch_fg', 'launch_input')
            self.visible_count, self.start = layout['visible_count'], layout['start']
            for hx, hy, hw, group in layout['headings']:
                put(hy, hx, group.upper(), hw, 'launch_muted')
            for rx, ry, rw, index in layout['cells']:
                entry = entries[index]
                selected = index == self.index
                title = entry['title'] + ('  · unavailable' if entry['missing'] else '')
                group_width = 13 if not layout['grouped'] and layout['columns'] == 1 and rw >= 54 else 0
                content = '  ' + ui.fit(title, rw - group_width - 3)
                if group_width:
                    content += ui.fit(entry['group'], group_width)
                put(ry, rx, content, rw,
                    'launch_bg' if selected else 'launch_muted' if entry['missing'] else 'launch_fg',
                    'launch_selection' if selected else 'launch_bg', selected)
                if selected:
                    put(ry, rx, '▌', 1, 'red', 'launch_selection')
                self.hits.append((rx, ry, rw, index))
            if not entries:
                put(y + 5, x, 'No matching actions. Ctrl+U clears the search.', width, 'launch_muted')
            if entries:
                entry = entries[self.index]
                put(layout['detail_y'], x, entry['missing'] or entry['description'], width, 'launch_secondary')
            footer = '↑↓ / Wheel  Select   Click / Enter  Open   Esc  Close   ?  Help'
            if width < 64:
                footer = 'Click / Enter  Open   Esc  Close   ?  Help'
            if width < 42:
                footer = 'Click / Enter   Esc   ?'
            put(layout['footer_y'], x, footer, width, 'launch_muted')
            counter = f'{self.index+1 if entries else 0}/{len(entries)}'
            if len(self.hits) < len(entries):
                counter += '  ↕'
            put(y + 1, x + width - len(counter), counter, len(counter), 'launch_muted')
        out.extend(('\x1b[22m', bg, fg))
        self.write(''.join(out))

    def move(self, delta):
        self.pressed = None
        if self.help:
            self.help_offset = max(0, self.help_offset + delta)
        else:
            count = len(ui.filtered(self.entries, self.query))
            self.index = max(0, min(self.index + delta, count - 1))
        self.draw()

    def move_column(self, direction):
        current = next((r for r in self.hits if r[3] == self.index), None)
        if current is None:
            return
        candidates = [r for r in self.hits if (r[0] - current[0]) * direction > 0]
        if candidates:
            self.pressed = None
            self.index = min(candidates, key=lambda r: abs(r[1] - current[1]))[3]
            self.draw()

    def activate(self):
        entries = ui.filtered(self.entries, self.query)
        if entries and not entries[self.index]['missing']:
            entry = entries[self.index]
            if entry['kind'] == 'help':
                self.help = True
                self.pressed = None
                self.draw()
            else:
                self.selected = entry['id']
                self.quit_loop(0)
        else:
            self.draw()  # A disabled row still explains why it is unavailable.

    def on_text(self, text, in_bracketed_paste=False):
        self.pressed = None
        if self.help:
            return
        if text == '?' and not self.query and not in_bracketed_paste:
            self.help = True
        else:
            self.query = (self.query + ui.clean(text))[:160]
            self.index = self.start = 0
        self.draw()

    def on_key(self, event):
        if event.is_release:
            return
        self.pressed = None
        if event.matches('escape'):
            if self.help:
                self.help = False
                self.draw()
            else:
                self.quit_loop(0)
        elif event.matches('down') or event.matches('tab'):
            self.move(1)
        elif event.matches('up') or event.matches('shift+tab'):
            self.move(-1)
        elif event.matches('left') and not self.help:
            self.move_column(-1)
        elif event.matches('right') and not self.help:
            self.move_column(1)
        elif event.matches('page_down'):
            self.move(self.visible_count)
        elif event.matches('page_up'):
            self.move(-self.visible_count)
        elif event.matches('home'):
            self.move(-10000)
        elif event.matches('end'):
            self.move(10000)
        elif event.matches('enter') and not self.help:
            self.activate()
        elif event.matches('backspace') and not self.help:
            self.query = self.query[:-1]
            self.index = self.start = 0
            self.draw()
        elif event.matches('ctrl+u') and not self.help:
            self.query = ''
            self.index = self.start = 0
            self.draw()
        elif event.matches('f1'):
            self.help = not self.help
            self.draw()

    def hit_at(self, event):
        return next((index for x, y, width, index in self.hits
                     if y == event.cell_y and x <= event.cell_x < x + width), None)

    def on_mouse_event(self, event):
        if event.buttons in (MouseButton.WHEEL_UP, MouseButton.WHEEL_DOWN):
            if event.type == EventType.PRESS:
                self.move(-1 if event.buttons == MouseButton.WHEEL_UP else 1)
            return
        hit = self.hit_at(event)
        if event.type == EventType.MOVE:
            position = (event.cell_x, event.cell_y)
            if self.pressed is not None and hit != self.pressed:
                self.pressed = None
            if position != self.mouse_position:
                self.mouse_position = position
                if hit is not None and hit != self.index:
                    self.index = hit
                    self.draw()
        elif event.buttons == MouseButton.LEFT:
            if event.type == EventType.PRESS:
                self.pressed = hit
                if hit is not None:
                    self.index = hit
                    self.draw()
            elif event.type == EventType.RELEASE:
                pressed, self.pressed = self.pressed, None
                if hit is not None and hit == pressed:
                    self.index = hit
                    self.activate()

    def on_interrupt(self):
        self.quit_loop(0)

    on_eot = on_interrupt


def main(args):
    menu = LaunchMenu()
    Loop().loop(menu)
    return menu.selected


def handle_result(args, answer, target_window_id, boss):
    if not answer:
        return
    window = boss.window_id_map.get(target_window_id)
    if window is None:
        return
    entry = next((item for item in ui.actions(CONFIG) if item['id'] == answer), None)
    if entry is None:
        return
    if entry['missing']:
        boss.show_error('Terminal', entry['missing'])
        return
    kind = entry['kind']

    def launch(type_, argv=(), extra=()):
        return boss.call_remote_control(window, ('launch', '--type=' + type_, '--cwd=current',
            '--self', *extra, '--', *argv))

    try:
        if kind == 'newtab':
            launch('tab')
        elif kind == 'newwindow':
            launch('os-window')
        elif kind in ('vsplit', 'hsplit'):
            tab = window.tabref()
            if tab is not None:
                tab.goto_layout('splits')
                launch('window', extra=('--location=' + kind,))
        elif kind == 'zoom':
            tab = window.tabref()
            if tab is not None:
                tab.toggle_layout('stack')
        elif kind == 'rename':
            from kitty.conf.utils import KeyAction
            boss.dispatch_action(KeyAction('set_tab_title', ()), window_for_dispatch=window)
        elif kind in ('tool', 'logs'):
            argv = entry['argv']
            if kind == 'logs':
                argv = [*argv, '--offer-elevation']
            launch('tab', argv, ('--tab-title=' + entry['title'], '--hold'))
        elif kind == 'external':
            launch('background', entry['argv'])
        elif kind == 'config':
            editor = next((shutil.which(x) for x in ('nano', 'micro', 'vim', 'vi') if shutil.which(x)), None)
            if not editor:
                raise RuntimeError('No terminal editor found. Edit ' + str(CONFIG / 'user.conf') + ' with your preferred editor.')
            launch('tab', (editor, str(CONFIG / 'user.conf')), ('--tab-title=User settings',))
        elif kind == 'restore':
            launch('tab', (shutil.which('python3') or 'python3', str(CONFIG / 'odyssey-local-manage.py'),
                          'restore', '--config-dir', str(CONFIG), '--ask'),
                   ('--tab-title=Restore configuration', '--hold'))
        elif kind == 'vanilla':
            from kitty.constants import kitty_exe
            subprocess.Popen([kitty_exe(), '--config', 'NONE'], start_new_session=True)
    except Exception as error:
        boss.show_error('Terminal · ' + entry['title'], str(error))
