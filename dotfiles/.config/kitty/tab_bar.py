"""Odyssey tabs: normal close clicks and readable, paged tab navigation.

Native tab selection, dragging, renaming and close confirmations remain owned
by Kitty. GPL-3.0-or-later.
"""
import importlib.util
from pathlib import Path

from kitty.boss import Boss
from kitty import fast_data_types as fdt
from kitty.fast_data_types import add_timer, get_boss
from kitty.tab_bar import TabBar, TabExtent, CellRange, as_rgb

_spec = importlib.util.spec_from_file_location('odyssey_terminal_ui', Path(__file__).with_name('odyssey_terminal.py'))
ui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ui)

# Keep the native methods, and replace our hooks rather than stacking wrappers.
if not hasattr(Boss, '_odyssey_terminal_mouse_original'):
    Boss._odyssey_terminal_mouse_original = Boss.handle_tab_bar_mouse
if not hasattr(TabBar, '_odyssey_terminal_update_original'):
    TabBar._odyssey_terminal_update_original = TabBar.update
if not hasattr(Boss, '_odyssey_terminal_mouse_state'):
    Boss._odyssey_terminal_mouse_state = {'zones': {}, 'pressed': {}}
STATE = Boss._odyssey_terminal_mouse_state
for _key in ('starts', 'order', 'absolute'):
    STATE.setdefault(_key, {})
LOCK_MODIFIERS = (getattr(fdt, 'GLFW_MOD_CAPS_LOCK', 0x0040) |
                  getattr(fdt, 'GLFW_MOD_NUM_LOCK', 0x0080))


def _rgb(name):
    return int(ui.PALETTE.get(name, name).lstrip('#'), 16)


def draw_tab(draw_data, screen, tab, before, max_title_length, index, is_last, extra_data):
    budget = max(0, min(max_title_length, screen.columns - before))
    if not budget:
        return before
    screen.cursor.bold = tab.is_active
    screen.cursor.italic = False
    screen.cursor.decoration = 0
    screen.cursor.bg = as_rgb(draw_data.tab_bg(tab))
    screen.cursor.fg = as_rgb(draw_data.tab_fg(tab))
    indicator = '! ' if tab.needs_attention else '• ' if tab.has_activity_since_last_focus else ''
    close_width = min(3, budget)
    screen.draw(ui.fit(' ' + indicator + ui.compact_title(tab.title), budget - close_width))
    start = screen.cursor.x
    screen.cursor.fg = as_rgb(_rgb('#918a81'))
    screen.cursor.bold = False
    screen.draw(' × ' if close_width == 3 else '× ' if close_width == 2 else '×')
    if not getattr(extra_data, 'for_layout', False):
        STATE['zones'].setdefault(draw_data.os_window_id, []).append(
            (start, screen.cursor.x, ('close', tab.tab_id)))
    return screen.cursor.x


def _update(self, data):
    osid = self.os_window_id
    if getattr(self, 'is_vertical', False) or fdt.get_options().tab_bar_style != 'custom':
        STATE['zones'][osid] = []
        STATE['absolute'][osid] = False
        return TabBar._odyssey_terminal_update_original(self, data)
    if not self.laid_out_once:
        return False
    self.last_laid_out_tabs = data
    self.num_tabs = len(data)
    STATE['order'][osid] = [t.tab_id for t in data]
    active = next((i for i, t in enumerate(data) if t.is_active), 0)
    s = self.screen
    layout = ui.tab_strip_layout(s.columns, len(data), active, STATE['starts'].get(osid, 0))
    STATE['starts'][osid] = layout['start']
    STATE['zones'][osid] = []
    STATE['absolute'][osid] = True
    s.cursor.x = s.cursor.y = 0
    s.cursor.bold = s.cursor.italic = False
    s.cursor.bg = as_rgb(_rgb('terminal'))
    s.cursor.fg = as_rgb(_rgb('terminal_text'))
    s.erase_in_line(2, False)
    for action, label in layout['buttons']:
        start = s.cursor.x
        disabled = ((action == 'previous' and active == 0) or
                    (action == 'next' and active >= len(data) - 1))
        s.cursor.fg = as_rgb(_rgb('#494641' if disabled else 'terminal_text'))
        s.draw(label)
        STATE['zones'][osid].append((start, s.cursor.x, action))
    extents = []
    for number, x, width in layout['tabs']:
        tab = data[number]
        s.cursor.x = x
        # Keep a separate cell for the divider, outside the native tab extent.
        end = draw_tab(self.draw_data, s, tab, x, max(1, width - 1), number + 1,
                       number == len(data) - 1, None)
        # Positional construction supports both cell_range (0.46) and x (0.48).
        extents.append(TabExtent(tab.tab_id, CellRange(x, max(x, end - 1))))
        if end < s.columns:
            s.cursor.bg = as_rgb(_rgb('terminal'))
            s.cursor.fg = as_rgb(_rgb('#494641'))
            s.draw('│')
    self.tab_extents = extents
    s.cursor.bold = s.cursor.italic = False
    s.cursor.bg = as_rgb(_rgb('terminal'))
    s.cursor.fg = as_rgb(_rgb('#a8a29b'))
    if layout['counter']:
        s.cursor.x = layout['counter_x']
        s.draw(layout['counter'])
    s.cursor.bg = s.cursor.fg = 0
    # Kitty 0.48 also refreshes the cached colors for the bar's outside margins.
    if hasattr(self, '_update_edge_defaults'):
        return self._update_edge_defaults(False)
    fdt.update_tab_bar_edge_colors(osid)
    return False


def _zone(boss, osid, x, y):
    tm = boss.os_window_map.get(osid)
    bar = getattr(tm, 'tab_bar', None)
    if bar is None or not getattr(bar, 'laid_out_once', False) or getattr(bar, 'is_vertical', False):
        return None
    g = bar.window_geometry
    if not (g.left <= x < g.right and g.top <= y < g.bottom):
        return None
    cell = int((x - g.left) // max(1, bar.cell_width))
    shift = 0
    if not STATE['absolute'].get(osid):
        extents = getattr(bar, 'tab_extents', ())
        shift = getattr(getattr(extents[0], 'x', getattr(extents[0], 'cell_range', None)), 'start', 0) if extents else 0
    for start, end, action in STATE['zones'].get(osid, ()):
        if start + shift <= cell < end + shift:
            return action
    return None


def _advance(boss, osid, delta):
    tm = boss.os_window_map.get(osid)
    active = getattr(tm, 'active_tab', None)
    order = STATE['order'].get(osid, ())
    if active is None or active.id not in order:
        return
    number = max(0, min(order.index(active.id) + delta, len(order) - 1))
    target = boss.tab_for_id(order[number])
    if target is not None and target.os_window_id == osid and target is not active:
        tm.set_active_tab(target)
        tm.update_tab_bar_data()
        tm.mark_tab_bar_dirty()


def _schedule(osid, window_id, action):
    def run(timer_id):
        boss = get_boss()
        if boss is None or osid not in boss.os_window_map:
            return
        try:
            if isinstance(action, tuple) and action[0] == 'close':
                target = boss.tab_for_id(action[1])
                if target is not None and target.os_window_id == osid:
                    boss.close_tab(target)
            elif action in ('previous', 'next'):
                _advance(boss, osid, -1 if action == 'previous' else 1)
            else:
                window = boss.window_id_map.get(window_id)
                if window is None:
                    return
                if action == 'launch':
                    boss.run_kitten_with_metadata(str(Path(__file__).with_name('odyssey-launch.py')), window=window)
                elif action == 'newtab':
                    boss.call_remote_control(window, ('launch', '--type=tab', '--cwd=current', '--self'))
        except Exception as error:
            boss.show_error('Terminal', str(error))
    add_timer(run, 0.01, False)


def _mouse(self, os_window_id, x, y, button, modifiers, action):
    original = Boss._odyssey_terminal_mouse_original
    shortcut_modifiers = modifiers & ~LOCK_MODIFIERS
    hit = _zone(self, os_window_id, x, y)
    pending = STATE['pressed'].get(os_window_id)
    if button == 0 and action == 1:
        STATE['pressed'].pop(os_window_id, None)
        pending = None
    if pending and button == -1:
        if hit != pending[0]:
            STATE['pressed'][os_window_id] = (None, pending[1])
        return
    if button == 0 and action == 1 and hit and not shortcut_modifiers:
        tm = self.os_window_map.get(os_window_id)
        tab = getattr(tm, 'active_tab', None)
        window = getattr(tab, 'active_window', None)
        STATE['pressed'][os_window_id] = (hit, window.id if window else 0)
        return
    if button == 0 and action == 0 and pending:
        STATE['pressed'].pop(os_window_id, None)
        if hit and hit == pending[0] and not shortcut_modifiers:
            _schedule(os_window_id, pending[1], hit)
        return
    return original(self, os_window_id, x, y, button, modifiers, action)


# Dispose of a v3/v4 hold if this file is loaded into a process using that code.
# No hold timer or mouse capture is installed by this revision.
_hold = STATE.pop('hold', None)
if _hold is not None:
    if _hold.get('timer') is not None:
        fdt.remove_timer(_hold['timer'])
    _boss = get_boss()
    if _boss is not None and _boss.mouse_handler is _hold.get('handler'):
        _boss.mouse_handler = _hold.get('previous_handler')
        fdt.redirect_mouse_handling(False)
STATE['pressed'].clear()
TabBar.update = _update
Boss.handle_tab_bar_mouse = _mouse
