#!/usr/bin/python3
"""Reversible, per-user Odyssey Terminal trial. GPL-3.0-or-later.

Never changes /usr, /etc, a package tree or another user's configuration.
Snapshots contain only the files this program is about to replace.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

VERSION = '2026.10.31-local5'
BEGIN = '# BEGIN ODYSSEY LOCAL TERMINAL'
END = '# END ODYSSEY LOCAL TERMINAL'
STATE = '.odyssey-local-state.json'
PAYLOAD = ('odyssey-ui.conf', 'odyssey_terminal.py', 'tab_bar.py', 'odyssey-launch.py',
           'odyssey-logviewer.py', 'odyssey-local-manage.py', 'odyssey-reset.sh')


def default_config():
    return Path(os.environ.get('KITTY_CONFIG_DIRECTORY') or
                str(Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'kitty')).expanduser()


def default_backups():
    packages = Path.home() / 'void-packages/srcpkgs'
    if packages.is_dir():
        return packages / 'BKG/odyssey-kitty-local'
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'odyssey/terminal-backups'


def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_atomic(path, data, mode=0o600):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.odyssey-write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def read_state(config):
    try:
        return json.loads((config / STATE).read_text())
    except (OSError, ValueError):
        return {}


def editable_files(config, names):
    for name in names:
        path = config / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError(f'{path} is a symlink or a non-regular file. Use preview; integrate this file through your dotfile manager.')


def snapshot(config, names, root, reason):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest = root / (stamp() + '-' + reason)
    dest.mkdir(mode=0o700)
    (dest / 'files').mkdir(mode=0o700)
    manifest = {'format': 1, 'config_dir': str(config), 'version': VERSION, 'reason': reason, 'files': {}}
    for name in names:
        source = config / name
        if source.exists():
            data = source.read_bytes()
            mode = source.stat().st_mode & 0o777
            # Backups may contain private configuration; keep their copies private.
            write_atomic(dest / 'files' / name, data, 0o600)
            manifest['files'][name] = {'exists': True, 'mode': mode, 'sha256': digest(data)}
        else:
            manifest['files'][name] = {'exists': False}
    write_atomic(dest / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
    return dest


def load_snapshot(path, config):
    manifest = json.loads((path / 'manifest.json').read_text())
    allowed = {*PAYLOAD, 'kitty.conf', 'user.conf', STATE}
    if manifest.get('format') != 1 or manifest.get('config_dir') != str(config):
        raise RuntimeError('The snapshot belongs to a different configuration directory or format.')
    if not isinstance(manifest.get('files'), dict) or not manifest['files']:
        raise RuntimeError('The snapshot has no file manifest.')
    for name, metadata in manifest['files'].items():
        if name not in allowed:
            raise RuntimeError('Unexpected snapshot filename: ' + name)
        if metadata.get('exists'):
            data = (path / 'files' / name).read_bytes()
            if digest(data) != metadata.get('sha256'):
                raise RuntimeError('Snapshot checksum mismatch: ' + name)
    return manifest


def replay_snapshot(path, config, manifest):
    for name, metadata in manifest['files'].items():
        if metadata.get('exists'):
            write_atomic(config / name, (path / 'files' / name).read_bytes(), metadata['mode'])
        else:
            (config / name).unlink(missing_ok=True)


def config_text(original):
    # Replace our block and move the two standard override includes to the end.
    begin, end = original.count(BEGIN), original.count(END)
    if begin != end or begin > 1:
        raise RuntimeError('Malformed Odyssey block in kitty.conf; no files changed.')
    if begin:
        left, rest = original.split(BEGIN, 1)
        _, right = rest.split(END, 1)
        original = left + right.removeprefix('\n')
    original = ''.join(line for line in original.splitlines(keepends=True)
                       if not re.fullmatch(r'\s*include[ \t]+(?:user|keybindings)\.conf[ \t]*(?:#.*)?\n?', line))
    return (original.rstrip('\n') + '\n\n' + BEGIN + '\n'
            '# Local trial. User settings and keybindings have final precedence.\n'
            'include odyssey-ui.conf\ninclude user.conf\ninclude keybindings.conf\n' + END + '\n')


def payload_data(source):
    result = {}
    for name in PAYLOAD:
        data = (source / name).read_bytes()
        if name.endswith('.py'):
            ast.parse(data, filename=name)
        result[name] = data
    return result


def apply(config, source, backups, preview=False):
    # Read and validate everything before creating a snapshot or replacing a file.
    payload = payload_data(source)
    config.mkdir(parents=True, exist_ok=True)
    original = (config / 'kitty.conf').read_text() if (config / 'kitty.conf').exists() else ''
    new_conf = config_text(original).encode()
    names = [*PAYLOAD, 'kitty.conf', STATE]
    create_user = not (config / 'user.conf').exists()
    if create_user:
        names.append('user.conf')
    editable_files(config, names)
    previous = snapshot(config, names, backups, 'before-apply')
    manifest = load_snapshot(previous, config)
    try:
        for name, data in payload.items():
            write_atomic(config / name, data, 0o755 if name.endswith('.sh') else 0o644)
        if create_user:
            write_atomic(config / 'user.conf', b'# Personal overrides. Loaded after the Odyssey theme.\n', 0o600)
        write_atomic(config / 'kitty.conf', new_conf, manifest['files']['kitty.conf'].get('mode', 0o600))
        state = {'version': VERSION, 'mode': 'preview' if preview else 'installed',
                 'backup': str(previous), 'backups': str(backups),
                 'files': {name: digest((config / name).read_bytes()) for name in names if name != STATE}}
        write_atomic(config / STATE, (json.dumps(state, indent=2) + '\n').encode())
    except BaseException:
        replay_snapshot(previous, config, manifest)
        raise
    return previous


def restore(config, backups=None, backup=None, ask=False):
    state = read_state(config)
    if state.get('mode') == 'preview' and backup is None:
        raise RuntimeError('This is an isolated preview. Close its window to discard it.')
    selected = backup or state.get('backup')
    if not selected:
        raise RuntimeError('No local installation snapshot found. Pass --backup to select an existing snapshot.')
    selected = Path(selected).expanduser().resolve()
    manifest = load_snapshot(selected, config)
    editable_files(config, manifest['files'])
    if ask:
        print('Restore the configuration saved before this local revision?')
        print('Snapshot:', selected)
        print('The current versions of these files will also be saved before restoring.')
        if input('Type RESTORE to continue: ').strip() != 'RESTORE':
            print('Cancelled. No files changed.')
            return None
    root = (backups or Path(state.get('backups') or selected.parent)).expanduser().resolve()
    rescue = snapshot(config, manifest['files'], root, 'before-restore')
    try:
        replay_snapshot(selected, config, manifest)
    except BaseException:
        replay_snapshot(rescue, config, load_snapshot(rescue, config))
        raise
    print('Restored:', selected)
    print('Configuration before restore saved at:', rescue)
    print('Open a new Kitty process to use the restored configuration.')
    return rescue


def preview(config, source, kitty):
    binary = shutil.which(kitty)
    if not binary:
        raise RuntimeError('Kitty executable not found: ' + kitty)
    with tempfile.TemporaryDirectory(prefix='odyssey-kitty-preview-') as temporary:
        root = Path(temporary)
        trial = root / 'kitty'
        if config.is_dir():
            shutil.copytree(config, trial)
        else:
            trial.mkdir()
        apply(trial, source, root / 'snapshots', preview=True)
        env = dict(os.environ, KITTY_CONFIG_DIRECTORY=str(trial))
        # Never join a running single-instance process: the old monkey patch
        # cannot reliably be undone by reloading configuration in that process.
        print('Isolated preview:', trial, flush=True)
        print('Odyssey Terminal revision:', VERSION, flush=True)
        print('Close every preview window before returning to this command.', flush=True)
        result = subprocess.run([binary, '--config', str(trial / 'kitty.conf'), '--class', 'odyssey-terminal-preview',
                                 '--title', 'Terminal · preview'], env=env)
        return result.returncode


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preview', 'apply', 'restore', 'status'))
    parser.add_argument('--config-dir', type=Path, default=default_config())
    parser.add_argument('--backup-root', type=Path)
    parser.add_argument('--backup', type=Path, help='Snapshot to restore instead of the latest installation snapshot')
    parser.add_argument('--kitty', default='kitty', help='Executable for an isolated preview')
    parser.add_argument('--ask', action='store_true', help='Ask before restoring; used by the graphical launcher')
    args = parser.parse_args(argv)
    config = args.config_dir.expanduser().resolve()
    source = Path(__file__).resolve().parent
    backups = (args.backup_root or default_backups()).expanduser().resolve()
    try:
        if args.command == 'preview':
            return preview(config, source, args.kitty)
        if args.command == 'apply':
            previous = apply(config, source, backups)
            print('Applied to:', config)
            print('Snapshot:', previous)
            print('Open a NEW Kitty process. The running one may still have the old mouse hook.')
        elif args.command == 'restore':
            restore(config, args.backup_root, args.backup, args.ask)
        elif args.command == 'status':
            print('Configuration:', config)
            state = read_state(config)
            if not state:
                print('No local revision is registered.')
            else:
                print(json.dumps(state, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print('Terminal:', error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
