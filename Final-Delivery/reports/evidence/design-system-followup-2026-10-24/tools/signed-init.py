# test-only: signed Bale mini-app init_data for the preview member (test bot token from the test suite)
import sys, time, json, hmac, hashlib
from urllib.parse import urlencode
BOT_TOKEN = "test-only-bale-token"
uid = int(sys.argv[1]); now = int(time.time())
fields = {"auth_date": str(now), "query_id": f"preview-{uid}-{now}", "user": json.dumps({"id": uid, "first_name": "آزمایش"}, ensure_ascii=False, separators=(",", ":"))}
check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
sig = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
print(urlencode([*fields.items(), ("hash", sig)]))
