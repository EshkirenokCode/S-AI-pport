#!/bin/sh
# Run from the deployed checkout; saves a consistent pair of synthetic databases.
set -eu
umask 077
backup_dir=${1:-/var/backups/saipport}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$backup_dir/$stamp"
compose() { docker compose -f compose.yaml -f deploy/compose.demo.yaml "$@"; }
trap 'compose start sandbox api worker' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
compose stop worker api sandbox
for database in saipport saipport_lab; do
  compose exec -T postgres pg_dump -U postgres -Fc "$database" > "$backup_dir/$stamp/$database.dump"
  compose exec -T postgres pg_restore --list < "$backup_dir/$stamp/$database.dump" > "$backup_dir/$stamp/$database.contents"
done
printf 'Saved database pair to %s\n' "$backup_dir/$stamp"
