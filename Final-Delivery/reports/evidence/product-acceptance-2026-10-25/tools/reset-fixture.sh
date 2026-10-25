#!/bin/bash
# Restore the live test DB from the pristine fixture (run only while the backend is stopped).
set -e
cp <local>/nora-fixture/nora.db <local>/nora-preview/nora-live.db
rm -f <local>/nora-preview/nora-live.db-wal <local>/nora-preview/nora-live.db-shm
echo "fixture restored: $(md5sum <local>/nora-fixture/nora.db | cut -c1-8) → nora-live.db"
