#!/bin/sh
# Keep the old entry point, with a timestamped, reversible restore.
set -eu
config_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$config_dir/odyssey-local-manage.py" restore --config-dir "$config_dir" --ask
