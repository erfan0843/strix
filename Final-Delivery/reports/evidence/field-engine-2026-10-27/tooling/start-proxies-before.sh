#!/bin/bash
# "before" UI proxies (owner :8010, manager :8011, member :8012) → old-UI backend :8002
C=<local>/nora-fixture/…
cd <local>
PORT=8010 BACKEND_PORT=8002 PREVIEW_ROLE=owner CREDS_FILE=$C node preview-proxy.cjs > /tmp/proxy-b-owner.log 2>&1 &
PORT=8011 BACKEND_PORT=8002 PREVIEW_ROLE=manager CREDS_FILE=$C PREVIEW_HOME='/admin.html#dash' node preview-proxy.cjs > /tmp/proxy-b-manager.log 2>&1 &
PORT=8012 BACKEND_PORT=8002 PREVIEW_ROLE=member CREDS_FILE=$C PREVIEW_HOME='/account.html' node preview-proxy.cjs > /tmp/proxy-b-member.log 2>&1 &
wait
