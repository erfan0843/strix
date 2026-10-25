#!/bin/bash
# Three role proxies (owner :8000, manager :8080, member :8090) → backend :8001; creds from the fixture login file (never printed)
C=<local>/nora-fixture/PREVIEW-LOGIN.local.md
cd <local>/nora-preview
PORT=8000 PREVIEW_ROLE=owner CREDS_FILE=$C node preview-proxy.cjs > /tmp/proxy-owner.log 2>&1 &
PORT=8080 PREVIEW_ROLE=manager CREDS_FILE=$C PREVIEW_HOME='/admin.html#dash' node preview-proxy.cjs > /tmp/proxy-manager.log 2>&1 &
PORT=8090 PREVIEW_ROLE=member CREDS_FILE=$C PREVIEW_HOME='/account.html' node preview-proxy.cjs > /tmp/proxy-member.log 2>&1 &
wait
