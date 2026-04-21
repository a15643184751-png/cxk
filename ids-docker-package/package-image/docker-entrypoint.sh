#!/bin/sh
set -eu

SOURCE_DIR="/opt/export/ids-docker-package"
TARGET_DIR="${TARGET_DIR:-/output}"
PACKAGE_NAME="${PACKAGE_NAME:-ids-docker-package}"
DEST_DIR="${TARGET_DIR%/}/${PACKAGE_NAME}"

mkdir -p "$TARGET_DIR"
rm -rf "$DEST_DIR"
cp -R "$SOURCE_DIR" "$DEST_DIR"

echo "Package exported to: $DEST_DIR"
echo "Next step:"
echo "  cd $DEST_DIR"
echo "  then run start-ids-docker.* or configure-ids-core.*"
