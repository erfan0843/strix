"""شواهد مرحلهٔ ۶: دفترکل واقعی ربات (SQLite آزمایشی) → همگام‌سازی HTTP واقعی با سرور آزمایشی."""
import json, os, sys
os.environ.update({
    "BOT_TOKEN": "1095412158:TEST_TOKEN_FOR_UNITTEST", "SUPER_ADMIN_ID": "100000001",
    "DB_PATH": "/tmp/qa/p6/bot/bot.db", "BACKUP_DIR": "/tmp/qa/p6/bot/backups", "IMPORT_DIR": "/tmp/qa/p6/bot/imports",
    "FILES_DIR": "/tmp/qa/p6/bot/files", "PROFILES_DIR": "/tmp/qa/p6/bot/files/profiles",
    "EVENTS_DIR": "/tmp/qa/p6/bot/files/events", "LOG_DIR": "/tmp/qa/p6/bot/logs",
    "NORA_SHARED_API_URL": "http://127.0.0.1:8000",
})
sys.path.insert(0, os.getcwd())
import database, points_ledger as pl, shared_api
database.init_db()
out = {}
for uid, name in ((910001, "عضو آزمایشی یک"), (910002, "عضو آزمایشی دو"), (910999, "بدون هویت سرور")):
    database.db_execute("INSERT OR IGNORE INTO users (bale_user_id, first_name) VALUES (?, ?)", (uid, name))
P = pl.post_points
rows = []
rows.append(P(910001, 50, entry_type="award", source="achievement", ref_key="ach:910001:first_event", reason="دستاورد: نخستین رویداد"))
rows.append(P(910001, 20, entry_type="award", source="event_finished", ref_key="evfin:7:910001", reason="پایان رویداد ۷"))
rows.append(P(910001, -40, entry_type="spend", source="reward_redeem", ref_key="redeem:4", reason="خرید پاداش ۴"))
rows.append(P(910001, 40, entry_type="refund", source="reward_reject_refund", ref_key="redeem-refund:4", reason="رد درخواست پاداش ۴"))
dup = P(910001, 50, entry_type="award", source="achievement", ref_key="ach:910001:first_event", reason="تکرار")
out["duplicate_ach_changed_balance"] = bool(dup.created)
rows.append(P(910002, 30, entry_type="award", source="attendance_session", ref_key="att:12:910002", reason="حضور جلسهٔ ۱۲"))
rows.append(P(910002, -10, entry_type="spend", source="payment_spend", ref_key="pay:tx-91", reason="پرداخت با امتیاز"))
man = P(910002, 5, entry_type="manual_adjust", source="admin_manual", ref_key="manual:evidence-p6-0001", reason="اصلاح دستی آزمایشی", actor_kind="admin", actor_id=100000001)
rows.append(man)
rows.append(pl.reverse_entry(man.entry_id, reason="برگشت اصلاح دستی", actor_kind="admin", actor_id=100000001))
rows.append(P(910999, 15, entry_type="award", source="achievement", ref_key="ach:910999:first_event", reason="کاربر بدون هویت سرور"))
out["ledger_rows"] = database.db_execute("SELECT COUNT(*) AS c FROM points_ledger", fetch="one")["c"]
out["balances"] = {u: pl.balance(u) for u in (910001, 910002, 910999)}
out["sync_1"] = pl.sync_pending(limit=50)
out["sync_2_retry_including_unmapped"] = pl.sync_pending(limit=50, include_unmapped=True)
out["shared_status"] = [dict(r) for r in database.db_execute("SELECT shared_status, COUNT(*) AS n FROM points_ledger GROUP BY shared_status", fetch="all")]
# بازپخش دستی یک ردیف: باید created=false بدهد و ردیف دوم نسازد
e = pl.get_entry(1)
import shared_certificates as sc
key = f"{sc.source_id(database.db_execute, create=False)}:1"
out["replay_entry_1"] = shared_api.submit_points_entry("910001", key, pl.build_sync_payload(e, source_key=key.split(':')[0]))
out["reconcile"] = pl.reconcile()
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
