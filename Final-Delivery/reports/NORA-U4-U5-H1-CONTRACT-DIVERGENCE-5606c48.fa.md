# اختلاف `5606c48` (شاخهٔ رابط) با قرارداد مرجع بک‌اند — فقط موارد واقعی

مرجع: `arena/840de336-strix` @ `5f530e7` (بک‌اند `6520787`) · قرارداد: `NORA-U4-U5-H1-BACKEND-CONTRACT-2026-10-22.fa.md`
بررسی‌شده: `arena/5705a11f-strix` @ `5606c48` «feat(admin-api): add scoped user records and people editing contract» (پیاده‌سازی موازی بک‌اند در شاخهٔ رابط).

رابط باید **فقط** به شکل مرجع وصل شود؛ `5606c48` نباید وارد مرجع شود (تصمیم هماهنگ‌کننده). مسیرها و مجوزها در هر دو یکسان‌اند؛ اختلاف در شکل پاسخ و معنای H1 است:

| مورد | `5606c48` | مرجع (`6520787`) | پیامد برای رابط |
|---|---|---|---|
| U4 جزئیات — ماسک | `answers` را خام برمی‌گرداند؛ فقط فیلد `col:false` حذف می‌شود → پاسخ نوع `mobile`/`nid` **بدون ماسک** می‌آید | `mobile` → `value:null, masked:"mobile", hint:۴ رقم`; `nid` → `value:null, masked:"national_id"` | رابط باید `masked` را رندر کند؛ هیچ‌وقت `value` خالی را «بی‌پاسخ» نشان ندهد |
| U4 جزئیات — پرداخت | فقط `payment_status` | `payment:{status,method[,amount,currency,transaction_id]}|null` + `finance_visible` | مبلغ فقط وقتی `finance_visible:true` |
| U4 جزئیات — سایر | ندارد | `registrant_name, companions[], receipt{uploaded,task_id,task_status}, attendance{checked_in,checked_in_at,checked_in_by}, form.version, updated_at` و `type` در هر answer | — |
| U4 فهرست | بدون `account_id`, `event_id`, `ticket_type` | دارد | — |
| U4 فیلتر answers | بر اساس فیلدهای **فعلی** فرم (`form.fields`) | بر اساس فیلدهای **منجمد در snapshot** پاسخ | با مرجع، حذف بعدی یک فیلد از فرم پاسخ قدیمی را پنهان نمی‌کند |
| U5 | `scope` همیشه `"account"`؛ `read_at`؛ بدون `delivery_state`/`has_bale_identity`/`source_task_id`؛ `link` نامعتبر → null | `scope: "account"|"audience"`; `read` (bool); `delivery_state` (queued/retrying/delivered/failed); `has_bale_identity`; `source_task_id` | وضعیت صف/تلاش/تحویل از `delivery_state` خوانده شود، نه محاسبهٔ رابط |
| **H1 — مدل** | `site_content.py` تغییر کرده: GET مالک ردیف‌های draft/hidden/private را با فلگ برمی‌گرداند و PATCH آن‌ها را ذخیره می‌کند (`sanitize_owner_people`, `owner_person`) → **پیش‌نویس/پنهان برای people ساخته شده** | بدون تغییر `site_content.py`؛ people **پیش‌نویس ندارد**، ذخیره = انتشار فوری؛ ردیف غیرعمومی در `rejected_rows.people` گزارش می‌شود (`non_public` / `missing_required_fields` / `invalid_row`) | رابط هیچ گزینهٔ پیش‌نویس/پنهان نسازد؛ قبل از ذخیره «انتشار فوری» را اعلام کند؛ `rejected_rows` را نمایش دهد |
| H1 — خطاها | `invalid_site_content_people`, `invalid_site_content_people_state` (422 برای ردیف نامعتبر) | ردیف نامعتبر **422 نمی‌دهد**؛ ۲۰۰ با `rejected_rows` (ردیف‌های معتبر ذخیره می‌شوند). 422 فقط: `duplicate_site_content_id`, `unexpected_site_content_fields`, `invalid_site_content_records`, `empty_site_content_update`, `invalid_site_content_version` | پس از ۲۰۰ همیشه `rejected_rows.people` بررسی شود |
| آزمون‌های بک‌اند در `5606c48` | `test_admin_user_records_api.py` + تغییر `test_site_content_api.py`/`test_partner_retention.py` روی مدل draft | مرجع: `test_admin_user_file_api.py`, `test_site_content_people_editor.py` | آزمون‌های `5606c48` با مرجع سبز نمی‌شوند؛ نباید منتقل شوند |

یکسان در هر دو (نیازی به تغییر نیست): مسیرها، `us_view`، 401/403/404 (`user_not_found`, `registration_not_found`)، حذف ردیف همراه و فرم غیرثبت‌نام، فیلتر سروری `account_id` در U5، `Cache-Control: no-store`، CSRF + `expected_version` + 409 در H1.

وضعیت مرجع پس از بازسازی sandbox (۲۰۲۶-۱۰-۲۲): HEAD `5f530e7` = origin؛ بک‌اند بدون تغییر.
