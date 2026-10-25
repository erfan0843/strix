#!/bin/bash
# Restore the live test DB from the pristine fixture (run only while the backend is stopped).
set -e
cp <local> <local>
rm -f <local> <local>
echo "fixture restored: $(md5sum <local> | cut -c1-8) → nora-live.db"
