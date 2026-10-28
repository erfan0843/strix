#!/bin/bash
set +e
export NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<local> NORA_REPO_UI=<local>
OUT=<local> mkdir -p $OUT; cd <local>
step(){ echo "=== $1 start $(date +%T)"; }
killchrome(){ for p in $(ps -eo pid,comm | awk '$2 ~ /chrom/ {print $1}'); do kill -9 $p 2>/dev/null; done; sleep 1; }
curl -s -o /dev/null -w "owner auth/me %{http_code}\n" http://127.0.0.1:8000/api/auth/me
killchrome; step e2e-event-file; timeout 900 node e2e-event-file.cjs $OUT/e2e-event-file > $OUT/e2e-event-file.log 2>&1; echo "e2e-event-file EXIT $?"; tail -3 $OUT/e2e-event-file.log
export NORA_E2E_IDS=$OUT/e2e-event-file/ids.json
killchrome; step e2e-roles; timeout 600 node e2e-event-file-roles.cjs $OUT/e2e-roles > $OUT/e2e-roles.log 2>&1; echo "e2e-roles EXIT $?"; tail -2 $OUT/e2e-roles.log
killchrome; step e2e-builder-return; timeout 900 node e2e-builder-return.cjs $OUT/e2e-builder > $OUT/e2e-builder.log 2>&1; echo "e2e-builder EXIT $?"; tail -2 $OUT/e2e-builder.log
killchrome; step a11y; timeout 600 node a11y-after.cjs $OUT/a11y > $OUT/a11y.log 2>&1; echo "a11y EXIT $?"; tail -2 $OUT/a11y.log
killchrome; step g-shots; timeout 900 node g-shots.cjs $OUT/g-shots > $OUT/g-shots.log 2>&1; echo "g-shots EXIT $?"; tail -2 $OUT/g-shots.log
killchrome; step ds-audit; timeout 1200 node ds-audit.cjs $OUT/ds-audit > $OUT/ds-audit.log 2>&1; echo "ds-audit EXIT $?"; tail -3 $OUT/ds-audit.log
killchrome
curl -s -o /dev/null -w "owner auth/me after %{http_code}\n" http://127.0.0.1:8000/api/auth/me
step node-suite; cd <local> : > $OUT/node-suite.log
for f in *.test.mjs; do NODE_OPTIONS=--max-old-space-size=3072 timeout 280 node $f > /tmp/nt.log 2>&1; rc=$?; echo "$f exit=$rc fail-marks=$(grep -c '✗' /tmp/nt.log)" >> $OUT/node-suite.log; if [ $rc -ne 0 ]; then echo "--- $f output tail" >> $OUT/node-suite.log; tail -15 /tmp/nt.log >> $OUT/node-suite.log; fi; done
echo "node-suite done: $(grep -c 'exit=0' $OUT/node-suite.log)/$(grep -c 'exit=' $OUT/node-suite.log) exit 0"
step pytest; cd <local> timeout 600 <local> -m pytest -p no:cacheprovider -q -rs > $OUT/pytest.log 2>&1; echo "pytest EXIT $?"; tail -2 $OUT/pytest.log
step mypy; cd <local> timeout 120 <local> tools/run-python-tests.py types > $OUT/mypy.log 2>&1; echo "mypy EXIT $?"; tail -2 $OUT/mypy.log
step pg-migrations; cd <local> NORA_TEST_POSTGRES_URL='postgresql://postgres:@/postgres?host=<local>' PYTHONPATH=<local> timeout 600 <local> -m pytest -p no:cacheprovider -q -rs tests/test_migrations_postgres.py > $OUT/pg.log 2>&1; echo "pg EXIT $?"; tail -2 $OUT/pg.log
cd <local> killchrome; step audit-shots-after; SEED_IDS='{"paid":"ev-303b8522d5","free":"ev-5f6e2cd6a0","plain":"ev-7c4ccb5a2b","upcoming":"ev-d51453a8b1"}' timeout 1200 node audit-shots.cjs <local> > $OUT/audit-shots.log 2>&1; echo "audit-shots EXIT $?"; tail -2 $OUT/audit-shots.log
killchrome
echo "=== ALL DONE $(date +%T)"
