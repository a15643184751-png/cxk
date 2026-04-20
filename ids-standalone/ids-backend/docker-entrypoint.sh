#!/bin/sh
set -eu

python init_ids_db.py

exec "$@"
