#!/bin/bash
set -e

echo "Application entrypoint";

for f in /app-entrypoint.d/*; do
    echo "File: $f";
    case "$f" in
	*.sh)     echo "$0: running $f"; . "$f" ;;
	*)        echo "$0: ignoring $f" ;;
    esac
    echo
done

exec "$@";
