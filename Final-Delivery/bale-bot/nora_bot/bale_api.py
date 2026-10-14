"""
ارتباط با API بله - نسخه 5.0
مطابق مستندات رسمی docs.bale.ai

متدهای پیاده‌سازی شده:
  پیام:     sendMessage, editMessageText, editMessageCaption, editMessageReplyMarkup,
            deleteMessage, forwardMessage, copyMessage, sendChatAction
  رسانه:    sendPhoto, sendDocument, sendVideo, sendAudio, sendVoice, sendAnimation,
            sendMediaGroup, sendLocation, sendContact
  فایل:     getFile + دانلود
  چت:       getChat, getChatMember, getChatAdministrators, getChatMembersCount,
            banChatMember, unbanChatMember, promoteChatMember,
            pinChatMessage, unpinChatMessage, createChatInviteLink, exportChatInviteLink
  تعامل:    answerCallbackQuery, setMessageReaction (لایک), askReview
  پرداخت:   sendInvoice, createInvoiceLink, answerPreCheckoutQuery, inquireTransaction
  وبهوک:    setWebhook, deleteWebhook, getWebhookInfo
"""
import json
import queue
import threading
import time
import requests
from requests.adapters import HTTPAdapter

from config import API_URL, FILE_URL, AUTO_REACT_EMOJI, NORA_WEBAPP_URL
from database import log

MAX_LEN = 4000  # حاشیه امن زیر محدودیت 4096 مستندات

_session = requests.Session()
_session.mount("https://", HTTPAdapter(pool_connections=20, pool_maxsize=40))


# ==================== صف پس‌زمینه ====================
"""
🔴 باگ بحرانی که رفع شد:
   ربات تک‌نخی است. اگر یک متد غیرضروری (مثل setMessageReaction یا
   answerCallbackQuery) تایم‌اوت شود، کل ربات ۱۵-۳۰ ثانیه یخ می‌زند.

   نتیجه: «دکمه بازگشت کار نمی‌کند»، «مرحله بعد نمی‌رود»،
          «/start کار نمی‌کند» — چون ربات مشغول انتظار است.

   ✅ راه‌حل: متدهای «بهتره باشه ولی حیاتی نیست» در یک نخ جدا
      و با تایم‌اوت کوتاه اجرا می‌شوند. ربات منتظرشان نمی‌ماند.
"""

_bg_queue = queue.Queue(maxsize=500)
_bg_started = False
_bg_lock = threading.Lock()

# متدهایی که اگر کار نکنند مهم نیست — نباید ربات را بخوابانند
FIRE_AND_FORGET = {
    "setMessageReaction",
    "answerCallbackQuery",
    "askReview",
    "sendChatAction",
}

# متدهایی که بله ممکن است نداشته باشد — بعد از چند شکست خاموش می‌شوند
_unsupported = {}
_fail_count = {}
UNSUPPORTED_THRESHOLD = 3


def _bg_worker():
    while True:
        try:
            item = _bg_queue.get()
            if item is None:
                break
            method, params = item
            try:
                _raw_call(method, params, timeout=6, retries=0)
            except Exception:
                pass
            finally:
                _bg_queue.task_done()
        except Exception:
            time.sleep(0.5)


def _ensure_bg():
    global _bg_started
    with _bg_lock:
        if _bg_started:
            return
        for _ in range(2):
            t = threading.Thread(target=_bg_worker, daemon=True,
                                 name="nora-bg")
            t.start()
        _bg_started = True


def _mark_fail(method, desc=""):
    """اگر متدی چند بار پشت‌سرهم شکست خورد، دیگر صدایش نزن"""
    d = str(desc).lower()
    hard = any(k in d for k in ("not found", "unknown method", "bad request",
                                "does not exist", "invalid method"))
    _fail_count[method] = _fail_count.get(method, 0) + 1
    if hard or _fail_count[method] >= UNSUPPORTED_THRESHOLD:
        if method not in _unsupported:
            _unsupported[method] = True
            log(f"⚠️ متد {method} توسط بله پشتیبانی نمی‌شود — غیرفعال شد")


def _mark_ok(method):
    _fail_count.pop(method, None)


def api_async(method, params=None):
    """اجرای غیرمسدودکننده — ربات منتظر نمی‌ماند"""
    if _unsupported.get(method):
        return {"ok": True, "skipped": True}
    _ensure_bg()
    try:
        _bg_queue.put_nowait((method, params or {}))
    except queue.Full:
        pass
    return {"ok": True, "queued": True}


# ==================== CORE ====================
def api(method, params=None, retries=2, timeout=25):
    """
    درخواست به API بله.

    ✅ متدهای غیرحیاتی (ری‌اکشن، answerCallback، askReview، chatAction)
       به صف پس‌زمینه می‌روند تا ربات یخ نزند.
    """
    if method in FIRE_AND_FORGET:
        return api_async(method, params)
    return _raw_call(method, params, retries=retries, timeout=timeout)


def _raw_call(method, params=None, retries=2, timeout=25):
    """فراخوانی واقعی (مسدودکننده)"""
    if _unsupported.get(method):
        return {"ok": False, "description": "unsupported (disabled)",
                "skipped": True}

    url = f"{API_URL}/{method}"
    last = {"ok": False, "description": "پاسخی از بله دریافت نشد.", "error_code": "no_response"}

    for attempt in range(retries + 1):
        try:
            r = _session.post(url, json=params or {}, timeout=timeout)

            if r.status_code == 429:
                try:
                    wait = int(r.json().get("parameters", {}).get("retry_after", 3))
                except Exception:
                    wait = 3
                log(f"⏳ Rate limit روی {method} — {wait} ثانیه صبر")
                time.sleep(min(wait, 30))
                continue

            try:
                data = r.json()
            except Exception:
                data = {"ok": False, "description": f"پاسخ نامعتبر {r.status_code}"}

            if not data.get("ok"):
                desc = str(data.get("description", "")).lower()
                if method in FIRE_AND_FORGET or "method" in desc:
                    _mark_fail(method, desc)
                # این خطاها retry ندارند
                if any(k in desc for k in
                       ("blocked", "not found", "chat not found", "forbidden",
                        "deactivated", "bad request")):
                    return data
                last = data
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
            else:
                _mark_ok(method)
            return data

        except requests.exceptions.Timeout:
            last = {"ok": False, "description": "پاسخ بله به‌موقع نرسید؛ دوباره تلاش کن.", "error_code": "timeout"}
            if method in FIRE_AND_FORGET:
                _mark_fail(method, "timeout")
                return last
        except requests.exceptions.RequestException:
            # requests exceptions may contain the bot token inside the URL.
            last = {"ok": False, "description": "ارتباط با بله برقرار نشد؛ دوباره تلاش کن.",
                    "error_code": "transport_unavailable"}

        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))

    log(f"❌ API {method}: {last.get('description')}")
    # گزارش به سوپرادمین در حالت عیب‌یابی
    try:
        from database import get_setting
        if get_setting("debug_mode", "0") == "1" and method != "sendMessage":
            from config import SUPER_ADMIN_ID
            if SUPER_ADMIN_ID:
                api("sendMessage", {
                    "chat_id": SUPER_ADMIN_ID,
                    "text": f"🐞 خطای API\n\nمتد: {method}\nخطا: {last.get('description')}"
                }, retries=0)
    except Exception:
        pass
    return last


def _split_text(text, limit=MAX_LEN):
    """شکستن متن طولانی روی مرز خط"""
    text = str(text or "")
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            parts.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) + 1 > limit:
            if cur:
                parts.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        parts.append(cur)
    return parts


# ==================== پیام ====================
# آیا بله از copy_text پشتیبانی می‌کند؟ (خودکار تشخیص داده می‌شود)
_supports_copy_text = {"v": None}


def _strip_copy_text(kb):
    """
    حذف دکمه‌های copy_text و تبدیل به متن ساده.
    ⚠️ فیکس مهم: اگر بله copy_text را نشناسد، کل sendMessage خطا می‌دهد
    و کاربر هیچ پیامی نمی‌بیند → «دکمه کار نمی‌کند».
    """
    if not isinstance(kb, dict) or "inline_keyboard" not in kb:
        return kb, False
    changed = False
    rows = []
    for row in kb.get("inline_keyboard", []):
        new_row = []
        for b in row:
            if isinstance(b, dict) and "copy_text" in b:
                changed = True
                continue  # حذف دکمه کپی
            new_row.append(b)
        if new_row:
            rows.append(new_row)
    if not changed:
        return kb, False
    return ({"inline_keyboard": rows} if rows else None), True


def _has_copy_text(kb):
    if not isinstance(kb, dict):
        return False
    for row in kb.get("inline_keyboard", []):
        for b in row:
            if isinstance(b, dict) and "copy_text" in b:
                return True
    return False


def send(cid, text, kb=None, reply_to=None):
    """ارسال پیام متنی (با شکستن خودکار پیام بلند)"""
    if cid is None:
        return {"ok": False}

    # اگر قبلاً معلوم شده بله copy_text ندارد، از اول حذفش کن
    if kb and _supports_copy_text["v"] is False and _has_copy_text(kb):
        kb, _ = _strip_copy_text(kb)

    chunks = _split_text(text)
    result = {"ok": False}
    for i, chunk in enumerate(chunks):
        p = {"chat_id": cid, "text": chunk}
        if kb and i == len(chunks) - 1:
            p["reply_markup"] = kb
        if reply_to and i == 0:
            p["reply_to_message_id"] = reply_to
        result = api("sendMessage", p)

        # اگر به‌خاطر copy_text خطا خورد، بدون آن دوباره تلاش کن
        if (not result.get("ok") and kb and i == len(chunks) - 1
                and _has_copy_text(kb)):
            clean, changed = _strip_copy_text(kb)
            if changed:
                _supports_copy_text["v"] = False
                log("⚠️ بله از copy_text پشتیبانی نمی‌کند — دکمه‌های کپی حذف شدند")
                p2 = {"chat_id": cid, "text": chunk}
                if clean:
                    p2["reply_markup"] = clean
                result = api("sendMessage", p2)
        elif result.get("ok") and _has_copy_text(kb or {}):
            _supports_copy_text["v"] = True

        if len(chunks) > 1:
            time.sleep(0.4)
    return result


def edit_message(cid, mid, text, kb=None):
    p = {"chat_id": cid, "message_id": mid, "text": _split_text(text)[0]}
    if kb:
        p["reply_markup"] = kb
    return api("editMessageText", p)


# ==================== ویرایش هوشمند ====================
"""
معماری درست ویرایش پیام:

  ❌ روش غلط (قبلی): دیکشنری سراسری _last_menu
     مشکل: اگر کاربر روی دکمه پیام قدیمی بزند، پیام جدیدتر ویرایش می‌شود
           و کاربر تغییری نمی‌بیند → «دکمه کار نمی‌کند»

  ✅ روش درست: message_id از خود callback_query گرفته می‌شود
     هر کلیک، دقیقاً همان پیامی را ویرایش می‌کند که رویش کلیک شده.

قانون طلایی:
  • آمده از callback  → ویرایش همان پیام
  • آمده از پیام متنی → پیام جدید (چون پیامی برای ویرایش نیست)
  • کیبورد reply لازم → همیشه پیام جدید (reply در ویرایش کار نمی‌کند)
"""

# context هر آپدیت — توسط main.py قبل از هر هندلر ست می‌شود
_ctx = {}

# context کاربر جاری (برای انتخاب کیبورد درست در kb_remove)
#   admin = ادمین است؟   full = ادمین کامل/سوپرادمین است؟
_cur = {"admin": False, "full": False, "cid": None}


def set_context(chat_id, message_id=None, from_callback=False,
                is_admin=None, is_full=None):
    """قبل از پردازش هر آپدیت صدا زده می‌شود"""
    _ctx[chat_id] = {"mid": message_id, "cb": bool(from_callback)}
    _cur["cid"] = chat_id
    if is_admin is not None:
        _cur["admin"] = bool(is_admin)
    if is_full is not None:
        _cur["full"] = bool(is_full)


def clear_context(chat_id):
    _ctx.pop(chat_id, None)


def _ctx_mid(cid):
    c = _ctx.get(cid) or {}
    return c.get("mid") if c.get("cb") else None


def from_callback(cid):
    """آیا آپدیت جاری از کلیک روی دکمه شیشه‌ای آمده است؟"""
    return bool((_ctx.get(cid) or {}).get("cb"))


def _is_reply_kb(kb):
    """آیا کیبورد از نوع reply (پایین صفحه) است؟"""
    if not isinstance(kb, dict):
        return False
    return ("keyboard" in kb) or ("remove_keyboard" in kb)


def send_or_edit(cid, text, kb=None, mid=None, force_new=False):
    """
    اگر این فراخوانی از یک دکمه آمده، همان پیام را ویرایش می‌کند.
    در غیر این صورت پیام جدید می‌فرستد.

    خودکار پیام جدید می‌فرستد وقتی:
      • از callback نیامده باشد
      • کیبورد reply لازم باشد (در ویرایش پشتیبانی نمی‌شود)
      • متن طولانی‌تر از یک پیام باشد
      • ویرایش با خطا مواجه شود
    """
    if force_new or _is_reply_kb(kb):
        return send(cid, text, kb)

    target = mid or _ctx_mid(cid)
    if not target:
        return send(cid, text, kb)

    body = _split_text(text)
    if len(body) > 1:
        return send(cid, text, kb)

    # اگر می‌دانیم copy_text پشتیبانی نمی‌شود، از اول حذفش کن
    if kb and _supports_copy_text["v"] is False and _has_copy_text(kb):
        kb, _ = _strip_copy_text(kb)

    p = {"chat_id": cid, "message_id": target, "text": body[0]}
    if kb:
        p["reply_markup"] = kb

    r = api("editMessageText", p, retries=0, timeout=12)
    if r.get("ok"):
        if _has_copy_text(kb or {}):
            _supports_copy_text["v"] = True
        return r

    desc = str(r.get("description", "")).lower()
    if "not modified" in desc:
        return {"ok": True, "result": {"message_id": target}}

    # اگر به‌خاطر copy_text خطا خورد، بدون آن ویرایش کن
    if kb and _has_copy_text(kb) and ("button" in desc or "invalid" in desc):
        clean, changed = _strip_copy_text(kb)
        if changed:
            _supports_copy_text["v"] = False
            log("⚠️ بله از copy_text پشتیبانی نمی‌کند — دکمه‌های کپی حذف شدند")
            p2 = {"chat_id": cid, "message_id": target, "text": body[0]}
            if clean:
                p2["reply_markup"] = clean
            r2 = api("editMessageText", p2, retries=0, timeout=12)
            if r2.get("ok"):
                return r2
            return send(cid, text, clean)

    # ویرایش ممکن نشد → پیام جدید (send خودش copy_text را مدیریت می‌کند)
    return send(cid, text, kb)


# سازگاری با کد قبلی
def remember_menu(cid, res):
    pass


def forget_menu(cid):
    clear_context(cid)


def edit_caption(cid, mid, caption, kb=None):
    p = {"chat_id": cid, "message_id": mid, "caption": caption[:4000]}
    if kb:
        p["reply_markup"] = kb
    return api("editMessageCaption", p)


def edit_markup(cid, mid, kb):
    return api("editMessageReplyMarkup", {
        "chat_id": cid, "message_id": mid, "reply_markup": kb
    })


def delete_message(cid, mid):
    return api("deleteMessage", {"chat_id": cid, "message_id": mid})


def forward_message(cid, from_cid, mid):
    return api("forwardMessage", {
        "chat_id": cid, "from_chat_id": from_cid, "message_id": mid
    })


def copy_message(cid, from_cid, mid):
    """کپی پیام بدون لینک به پیام اصلی — برای اطلاع‌رسانی همگانی"""
    return api("copyMessage", {
        "chat_id": cid, "from_chat_id": from_cid, "message_id": mid
    })


def send_chat_action(cid, action="typing"):
    """
    نمایش وضعیت «در حال تایپ...» به کاربر.
    action: typing | upload_photo | record_video | upload_video |
            record_voice | upload_voice | choose_sticker
    """
    return api_async("sendChatAction", {"chat_id": cid, "action": action})


# ==================== ری‌اکشن (لایک) ====================
def set_reaction(cid, mid, emoji=None, is_big=False):
    """
    گذاشتن ری‌اکشن روی پیام (پیش‌فرض ❤️).

    ✅ کاملاً غیرمسدودکننده — در نخ پس‌زمینه اجرا می‌شود.
       اگر بله پشتیبانی نکند، بعد از چند تلاش خودکار خاموش می‌شود
       و دیگر هرگز ربات را کند نمی‌کند.
    """
    emoji = emoji or AUTO_REACT_EMOJI
    return api_async("setMessageReaction", {
        "chat_id": cid,
        "message_id": mid,
        "reaction": [{"type": "emoji", "emoji": emoji}],
    })


def set_reaction_sync(cid, mid, emoji=None):
    """نسخه مسدودکننده — فقط برای doctor.py"""
    emoji = emoji or AUTO_REACT_EMOJI
    payload = {"chat_id": cid, "message_id": mid,
               "reaction": [{"type": "emoji", "emoji": emoji}]}
    r = _raw_call("setMessageReaction", payload, retries=0, timeout=10)
    if not r.get("ok"):
        alt = {"chat_id": cid, "message_id": mid,
               "reaction": json.dumps([{"type": "emoji", "emoji": emoji}])}
        r2 = _raw_call("setMessageReaction", alt, retries=0, timeout=10)
        if r2.get("ok"):
            return r2
    return r


def clear_reaction(cid, mid):
    return api("setMessageReaction", {
        "chat_id": cid, "message_id": mid, "reaction": []
    }, retries=0, timeout=15)


# ==================== رضایت‌سنجی ====================
def ask_review(user_id, delay_seconds=5):
    """
    نمایش فرم رضایت‌سنجی به کاربر (از آبان ۱۴۰۴ در بله).
    بهترین زمان: بلافاصله بعد از یک عملیات موفق.
    """
    return api_async("askReview", {
        "user_id": user_id, "delay_seconds": int(delay_seconds)})


# ==================== رسانه ====================
def _send_file(method, field, cid, path_or_id, caption=None, kb=None, extra=None, filename=None, content_type=None):
    """ارسال فایل — هم مسیر محلی هم file_id/URL"""
    data = {"chat_id": str(cid)}
    if caption:
        data["caption"] = caption[:4000]
    if kb:
        data["reply_markup"] = json.dumps(kb, ensure_ascii=False)
    if extra:
        data.update({k: str(v) for k, v in extra.items()})

    s = str(path_or_id)
    # file_id یا URL → بدون آپلود
    if s.startswith("http") or (len(s) < 200 and "/" not in s and "\\" not in s):
        data[field] = s
        return api(method, {**{k: v for k, v in data.items() if k != "reply_markup"},
                            **({"reply_markup": kb} if kb else {})})

    try:
        with open(s, "rb") as f:
            upload = (filename, f, content_type or "application/octet-stream") if filename else f
            r = _session.post(f"{API_URL}/{method}", data=data,
                              files={field: upload}, timeout=180)
            return r.json()
    except FileNotFoundError:
        log(f"⚠️ فایل یافت نشد: {s}")
        return {"ok": False, "description": "file not found"}
    except Exception as e:
        log(f"❌ {method}: {e}")
        return {"ok": False, "description": "فایل به بله ارسال نشد؛ دوباره تلاش کن.",
                "error_code": "upload_failed"}


def send_photo(cid, photo, caption=None, kb=None, filename=None, content_type=None):
    return _send_file("sendPhoto", "photo", cid, photo, caption, kb,
                      filename=filename, content_type=content_type)


def send_document(cid, doc, caption=None, kb=None, filename=None, content_type=None):
    return _send_file("sendDocument", "document", cid, doc, caption, kb,
                      filename=filename, content_type=content_type)


def send_video(cid, video, caption=None, kb=None):
    return _send_file("sendVideo", "video", cid, video, caption, kb)


def send_audio(cid, audio, caption=None, kb=None):
    return _send_file("sendAudio", "audio", cid, audio, caption, kb)


def send_voice(cid, voice, caption=None, kb=None):
    return _send_file("sendVoice", "voice", cid, voice, caption, kb)


def send_animation(cid, anim, caption=None, kb=None):
    return _send_file("sendAnimation", "animation", cid, anim, caption, kb)


def send_media_group(cid, media):
    """media: آرایه‌ای از InputMediaPhoto/Video/Document/Audio"""
    return api("sendMediaGroup", {"chat_id": cid, "media": media})


def send_location(cid, lat, lon, kb=None):
    p = {"chat_id": cid, "latitude": float(lat), "longitude": float(lon)}
    if kb:
        p["reply_markup"] = kb
    return api("sendLocation", p)


def send_contact(cid, phone, first_name, last_name=None, kb=None):
    p = {"chat_id": cid, "phone_number": str(phone), "first_name": first_name}
    if last_name:
        p["last_name"] = last_name
    if kb:
        p["reply_markup"] = kb
    return api("sendContact", p)


# ==================== فایل ====================
def get_file_info(fid):
    return api("getFile", {"file_id": fid})


def download_file(file_path):
    try:
        r = _session.get(f"{FILE_URL}/{file_path}", timeout=120)
        if r.status_code == 200:
            return r.content
        log(f"❌ دانلود ناموفق: HTTP {r.status_code}")
    except Exception as e:
        log(f"❌ دانلود: {e}")
    return None


# ==================== آپدیت‌ها ====================
def get_updates(offset=None, timeout=25, limit=100):
    p = {"timeout": timeout, "limit": min(limit, 100)}
    if offset is not None:
        p["offset"] = offset
    return api("getUpdates", p, retries=0, timeout=timeout + 15)


def get_me():
    return api("getMe", retries=1)


def set_webhook(url):
    return api("setWebhook", {"url": url})


def delete_webhook():
    return api("deleteWebhook")


def get_webhook_info():
    return api("getWebhookInfo")


# ==================== چت ====================
def get_chat(chat_id):
    return api("getChat", {"chat_id": chat_id}, retries=1, timeout=20)


def get_chat_member(chat_id, user_id):
    return api("getChatMember", {"chat_id": chat_id, "user_id": user_id},
               retries=1, timeout=20)


def get_chat_administrators(chat_id):
    return api("getChatAdministrators", {"chat_id": chat_id})


def get_chat_members_count(chat_id):
    return api("getChatMembersCount", {"chat_id": chat_id})


def ban_chat_member(chat_id, user_id):
    return api("banChatMember", {"chat_id": chat_id, "user_id": user_id})


def unban_chat_member(chat_id, user_id, only_if_banned=True):
    return api("unbanChatMember", {
        "chat_id": chat_id, "user_id": user_id, "only_if_banned": only_if_banned
    })


def pin_chat_message(chat_id, message_id):
    return api("pinChatMessage", {"chat_id": chat_id, "message_id": message_id})


def unpin_chat_message(chat_id, message_id):
    return api("unpinChatMessage", {"chat_id": chat_id, "message_id": message_id})


def create_chat_invite_link(chat_id):
    return api("createChatInviteLink", {"chat_id": chat_id})


def export_chat_invite_link(chat_id):
    return api("exportChatInviteLink", {"chat_id": chat_id})


# ==================== callback ====================
def answer_callback(cb_id, text=None, alert=False):
    """
    پاسخ به callback query.
    مطابق مستندات: اگر callback_query_id با «1» شروع شود،
    کاربر نسخه قدیمی دارد و متن نمایش داده نمی‌شود.
    """
    p = {"callback_query_id": cb_id}
    if text:
        p["text"] = text[:190]
        p["show_alert"] = bool(alert)
    # غیرمسدودکننده — ربات منتظر نمی‌ماند
    return api_async("answerCallbackQuery", p)


def supports_callback_text(cb_id):
    """آیا کلاینت کاربر از نمایش متن callback پشتیبانی می‌کند؟"""
    return not str(cb_id or "").startswith("1")


# ==================== پرداخت ====================
def send_invoice(cid, title, description, payload, provider_token,
                 prices, photo_url=None, reply_to=None):
    """
    ارسال درخواست پول کیف‌پولی.
    prices: [{"label": "بلیت", "amount": 500000}]  ← مبلغ به ریال
             (همان عددی که ادمین وارد کرده — بدون هیچ تبدیلی)
    """
    p = {
        "chat_id": cid,
        "title": str(title)[:32],
        "description": str(description)[:255],
        "payload": str(payload)[:128],
        "provider_token": provider_token,
        "prices": prices,
    }
    if photo_url:
        p["photo_url"] = photo_url
    if reply_to:
        p["reply_to_message_id"] = reply_to
    return api("sendInvoice", p)


def create_invoice_link(title, description, payload, provider_token, prices):
    """ساخت شناسه پرداخت برای مینی‌اپ"""
    return api("createInvoiceLink", {
        "title": str(title)[:32],
        "description": str(description)[:255],
        "payload": str(payload)[:128],
        "provider_token": provider_token,
        "prices": prices,
    })


def answer_pre_checkout_query(query_id, ok=True, error_message=None):
    """
    ⚠️ باید ظرف حداکثر ۱۰ ثانیه پاسخ داده شود، وگرنه پرداخت لغو می‌شود.
    """
    p = {"pre_checkout_query_id": query_id, "ok": bool(ok)}
    if not ok and error_message:
        p["error_message"] = str(error_message)[:200]
    return api("answerPreCheckoutQuery", p, retries=1, timeout=8)


def inquire_transaction(transaction_id):
    """استعلام وضعیت تراکنش: pending | paid | failed | rejected"""
    return api("inquireTransaction", {"transaction_id": str(transaction_id)},
               retries=1, timeout=20)


# ==================== KEYBOARDS ====================
BTN_BACK = "🔙 بازگشت"
BTN_SKIP = "⏭️ رد کردن"
BTN_CANCEL = "❌ انصراف"


def kb_auth():
    return {"inline_keyboard": [
        [{"text": "📱 اشتراک شماره تلفن", "callback_data": "auth_phone"}],
        [{"text": "🔢 تأیید دو مرحله‌ای (کد یکبار مصرف)", "callback_data": "auth_otp"}],
    ]}


def kb_contact():
    return {
        "keyboard": [
            [{"text": "📱 اشتراک شماره‌ام", "request_contact": True}],
            [{"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def kb_cancel():
    """کیبورد مرحله‌ای — همیشه راه فرار دارد"""
    return {"keyboard": [
        [{"text": BTN_BACK}],
        [{"text": "🏠 منوی اصلی"}],
    ], "resize_keyboard": True}


def kb_otp():
    return {
        "keyboard": [
            [{"text": "🔄 ارسال مجدد کد"}],
            [{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}],
        ],
        "resize_keyboard": True,
    }


def kb_skip():
    return {
        "keyboard": [
            [{"text": BTN_SKIP}],
            [{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}],
        ],
        "resize_keyboard": True,
    }


def kb_gender():
    return {
        "keyboard": [
            [{"text": "👨 مرد"}, {"text": "👩 زن"}],
            [{"text": BTN_SKIP}],
            [{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}],
        ],
        "resize_keyboard": True,
    }


def kb_education():
    return {
        "keyboard": [
            [{"text": "زیر دیپلم"}, {"text": "دیپلم"}],
            [{"text": "فوق دیپلم"}, {"text": "کارشناسی"}],
            [{"text": "کارشناسی ارشد"}, {"text": "دکترا"}],
            [{"text": "حوزوی"}, {"text": "سایر"}],
            [{"text": BTN_SKIP}],
            [{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}],
        ],
        "resize_keyboard": True,
    }


def kb_location():
    return {
        "keyboard": [
            [{"text": "📍 ارسال موقعیت من", "request_location": True}],
            [{"text": BTN_SKIP}],
            [{"text": BTN_BACK}],
        ],
        "resize_keyboard": True,
    }


def kb_remove():
    """
    بازگرداندن منوی اصلی پایین صفحه پس از پایان یک مرحله.

    نقش ادمین از context جاری خوانده می‌شود تا دکمه «پنل ادمین»
    برای ادمین‌ها حفظ شود (بدون نیاز به تغییر ۱۲۰+ فراخوانی).
    """
    return kb_persistent(_cur.get("admin", False), _cur.get("full", False))


# ==================== منوی اصلی پایین صفحه ====================
"""
🎯 معماری منو (طبق درخواست کاربر):

   ❌ قبلاً: منوی اصلی هم به‌صورت شیشه‌ای (inline) و هم پایین صفحه
             نمایش داده می‌شد → کاربر یک منو را دو بار می‌دید.

   ✅ حالا:  منوی اصلی فقط پایین صفحه (reply keyboard).
             کیبورد شیشه‌ای فقط برای محتوای داخل هر بخش
             (لیست رویدادها، تنظیمات، ...) استفاده می‌شود.

منوی پایین «چسبان» است و یک بار ارسال می‌شود؛ بعد از آن
پیام‌ها بدون کیبورد ارسال/ویرایش می‌شوند تا پیام اضافه ساخته نشود.
"""

BTN_EVENTS = "🎉 رویدادها"
BTN_FORMS = "📝 فرم‌ها"
BTN_PROFILE = "👤 پروفایل من"
BTN_ATTEND = "✋ حضور و غیاب"
BTN_INVITE = "👥 دعوت از دوستان"
BTN_NOTIF = "🔔 اعلان‌ها"
BTN_SUPPORT = "💬 پشتیبانی"
BTN_HOME = "🏠 منوی اصلی"
BTN_ADMIN = "👨‍💼 پنل ادمین"
BTN_WEBAPP = "🌐 نورا وب‌اپ"

# 🆕 فاز ۱۳ — منوی مخصوص سوپرادمین / ادمین کامل
BTN_ADM_EVENTS = "🎉 رویدادها"     # همان متن، ولی به پنل ادمینِ رویداد می‌رود
BTN_ADM_USERS = "👥 کاربران"
BTN_ADM_FORMS = "📝 فرم‌ساز"
BTN_ADM_REPORTS = "📊 گزارش‌ها"
BTN_ADM_SETTINGS = "⚙️ تنظیمات"
BTN_USER_VIEW = "👤 نمای کاربر"    # برای دیدن ربات از چشم کاربر عادی

# متن‌هایی که دکمه منوی اصلی پایین هستند (برای تشخیص در روتر)
MAIN_MENU_BUTTONS = {
    BTN_EVENTS, BTN_FORMS, BTN_PROFILE, BTN_ATTEND,
    BTN_INVITE, BTN_NOTIF, BTN_SUPPORT, BTN_HOME, BTN_ADMIN,
    BTN_ADM_USERS, BTN_ADM_FORMS, BTN_ADM_REPORTS, BTN_ADM_SETTINGS,
    BTN_USER_VIEW,
}


def kb_persistent(is_admin=False, is_full=False):
    """
    ✅ منوی اصلی — دکمه‌های پایین صفحه.
    همیشه در دسترس است، پس کاربر هیچ‌وقت گیر نمی‌افتد.

    🔴 فاز ۱۳ — درخواست صریح کاربر:
       «کلاً منوی کاربر معمولی به سوپر ادمین و ادمین کامل نشون نده»

       ┌─────────────┬───────────────────────────────────────┐
       │ سوپرادمین   │ منوی مدیریتی خالص (۶ دکمه)            │
       │ ادمین کامل  │ بدون «دعوت از دوستان»، «اعلان‌ها»، ... │
       ├─────────────┼───────────────────────────────────────┤
       │ ادمین جزئی  │ منوی کاربر + دکمه «پنل ادمین»         │
       │ کاربر عادی  │ منوی کاربر                            │
       └─────────────┴───────────────────────────────────────┘

       ادمین کامل هر وقت خواست ربات را از چشم کاربر ببیند،
       «👤 نمای کاربر» را می‌زند.

       اگر NORA_WEBAPP_URL تنظیم شده باشد، دکمهٔ Mini App به‌صورت یک ردیف
       اضافه می‌شود؛ منوی گفت‌وگویی و دکمه‌های قدیمی جایگزین نمی‌شوند.
    """
    if is_full:
        rows = [
            [{"text": BTN_ADMIN}],
            [{"text": BTN_ADM_EVENTS}, {"text": BTN_ADM_FORMS}],
            [{"text": BTN_ADM_USERS}, {"text": BTN_ADM_REPORTS}],
            [{"text": BTN_ADM_SETTINGS}, {"text": BTN_USER_VIEW}],
        ]
        if NORA_WEBAPP_URL:
            rows.append([{"text": BTN_WEBAPP, "web_app": {"url": NORA_WEBAPP_URL}}])
        return {"keyboard": rows, "resize_keyboard": True,
                "is_persistent": True}

    rows = [
        [{"text": BTN_EVENTS}, {"text": BTN_FORMS}],
        [{"text": BTN_PROFILE}, {"text": BTN_ATTEND}],
        [{"text": BTN_INVITE}, {"text": BTN_NOTIF}],
        [{"text": BTN_SUPPORT}, {"text": BTN_HOME}],
    ]
    if NORA_WEBAPP_URL:
        rows.append([{"text": BTN_WEBAPP, "web_app": {"url": NORA_WEBAPP_URL}}])
    if is_admin:
        rows.append([{"text": BTN_ADMIN}])
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


# چت‌هایی که منوی پایین برایشان ارسال شده (در همین اجرا)
_kb_sent = {}


def ensure_persistent(cid, is_admin=False, force=False, is_full=False):
    """
    منوی پایین را فقط وقتی لازم است می‌فرستد.

    اگر قبلاً با همین نقش ارسال شده باشد، دوباره ارسال نمی‌شود
    تا پیام اضافه ساخته نشود (درخواست کاربر: پیام جدید باز نکن).

    ⚠️ «نقش» حالا شامل is_full هم هست: اگر ادمین کامل «نمای کاربر»
       را بزند، کلید عوض می‌شود و کیبورد تازه ارسال می‌گردد.
    """
    key = (bool(is_admin), bool(is_full))
    if not force and _kb_sent.get(cid) == key:
        return False
    _kb_sent[cid] = key
    return True


def reset_persistent(cid=None):
    """فراموش کردن وضعیت منوی پایین (مثلاً بعد از تغییر نقش)"""
    if cid is None:
        _kb_sent.clear()
    else:
        _kb_sent.pop(cid, None)


def kb_hard_remove():
    """حذف واقعی کیبورد (فقط جاهای خاص)"""
    return {"remove_keyboard": True}


def kb_force_join(channels):
    btns = []
    for ch in channels or []:
        title = ch.get("channel_title") or ch.get("channel_username") or "کانال"
        link = (ch.get("invite_link") or "").strip()
        username = (ch.get("channel_username") or "").strip()
        if link:
            btns.append([{"text": f"📢 {title}", "url": link}])
        elif username and not username.startswith("-"):
            # 🌐 دامنه از config می‌آید تا در یک نقطه قابل تغییر باشد
            try:
                from config import BALE_DOMAIN as _D
            except Exception:
                _D = "https://ble.ir"
            btns.append([{"text": f"📢 {title}",
                          "url": f"{_D}/{username.lstrip('@')}"}])
        else:
            btns.append([{"text": f"🔒 {title} (لینک ندارد)", "callback_data": "noop"}])
    btns.append([{"text": "✅ بررسی عضویت", "callback_data": "check_join"}])
    return {"inline_keyboard": btns}


def kb_main(is_admin=False, is_full=False):
    """
    منوی اصلی = کیبورد پایین صفحه.

    ⚠️ قبلاً اینجا کیبورد شیشه‌ای برمی‌گشت و همزمان منوی پایین هم بود؛
       کاربر یک منو را دو بار می‌دید. حالا فقط منوی پایین برمی‌گردد.
    """
    return kb_persistent(is_admin, is_full)


def kb_main_inline(is_admin=False):
    """
    نسخه شیشه‌ای منوی اصلی — فقط برای دکمه «بازگشت» داخل صفحات.
    در خود منوی اصلی استفاده نمی‌شود.
    """
    btns = [
        [{"text": BTN_EVENTS, "callback_data": "u_events"},
         {"text": BTN_FORMS, "callback_data": "u_forms"}],
        [{"text": BTN_PROFILE, "callback_data": "profile_view"},
         {"text": BTN_ATTEND, "callback_data": "u_attendance"}],
        [{"text": BTN_INVITE, "callback_data": "u_referral"},
         {"text": BTN_NOTIF, "callback_data": "u_notifications"}],
        [{"text": "💬 پشتیبانی و درباره ما", "callback_data": "u_support"}],
    ]
    if is_admin:
        btns.append([{"text": BTN_ADMIN, "callback_data": "admin_panel"}])
    return {"inline_keyboard": btns}


def kb_profile(has_photo=False, status="draft", badges=None):
    """
    👤 منوی پروفایل — فاز ۳۸: جمع‌وجور و مرتب

    🎯 «قسمت پروفایل من تو منو کاربر خیلی شلخته‌س، جمع و جور و
        جامع‌تر و شیک‌ترش کن»

    🔴 مشکل نسخهٔ قبل: ۱۰ ردیف دکمهٔ تک‌ستونی پشت سر هم، بدون
       هیچ دسته‌بندی. دکمهٔ عکس هم اینجا بود در حالی که جایش
       داخل خودِ فرم پروفایل است.

    ✅ حالا: ۵ ردیف، سه دستهٔ روشن، دکمه‌های هم‌خانواده کنار هم.

        ✏️ پروفایل من            ← تکمیل/ویرایش (عکس هم داخلش)
        ─────────────────
        🎫 بلیت‌ها   🎓 گواهینامه‌ها      ← داشته‌های من
        📊 کارنامه   🏆 امتیاز
        ─────────────────
        🏅 باشگاه من                       ← سرگرمی
        💬 پشتیبانی
    """
    b = badges or {}

    def _tag(n):
        return f" ({n})" if n else ""

    fill = ("✏️ ویرایش پروفایل"
            if status in ("approved", "pending")
            else "📝 تکمیل پروفایل")

    return {"inline_keyboard": [
        # ─── ویرایش ───
        [{"text": fill, "callback_data": "profile_fill"}],
        # ─── داشته‌های من ───
        [{"text": f"🎫 بلیت‌ها{_tag(b.get('tickets'))}",
          "callback_data": "u_my_tickets"},
         {"text": f"🎓 گواهینامه‌ها{_tag(b.get('certs'))}",
          "callback_data": "u_my_certs"}],
        [{"text": "📊 کارنامه حضور", "callback_data": "u_att_report"},
         {"text": "🏆 امتیاز من", "callback_data": "u_points"}],
        # ─── باشگاه ───
        [{"text": "🏅 باشگاه من", "callback_data": "cl_my"}],
        # ─── پشتیبانی ───
        [{"text": f"💬 پشتیبانی{_tag(b.get('tk'))}",
          "callback_data": "tk_my"},
         {"text": "🔙 منوی اصلی", "callback_data": "back_main"}],
    ]}


def kb_admin(pending=0, pending_pay=0, uid=None, badges=None):
    """
    👨‍💼 پنل ادمین — فاز ۱۳: خلوت، جامع، بر اساس دسترسی

    🎯 درخواست کاربر: «کلاً پنل ادمین شلوغ نباشه و جامع باشه»

    ۱۲ دکمه → ۷ دکمه. چیزهایی که زیرمجموعه شدند:
      • 📋 درخواست‌های پروفایل  → 👥 مدیریت کاربران
      • 📋 لاگ فعالیت           → 👥 مدیریت کاربران › مدیریت ادمین‌ها
      • 💰 مالی و تراکنش‌ها     → ⚙️ تنظیمات › روش‌های پرداخت (فقط سوپرادمین)
      • 🎉 تعریف رویداد جدید    → داخل «رویدادها»
      • 📱 تیکت + 🏅 باشگاه     → 💬 پشتیبانی و باشگاه

    هر دکمه فقط وقتی نمایش داده می‌شود که ادمین دسترسی‌اش را داشته باشد.
    """
    b = badges or {}
    rows = []

    def can(section):
        if uid is None:
            return True
        try:
            import permissions as _pm
            return _pm.can_section(uid, section)
        except Exception:
            return True

    if can("events"):
        n = b.get("events") or 0
        rows.append([{"text": f"🎉 رویدادها ({n})" if n else "🎉 رویدادها",
                      "callback_data": "ev_list"}])
    if can("forms"):
        rows.append([{"text": "📝 فرم‌ساز", "callback_data": "fb_panel"}])
    if can("users"):
        lbl = "👥 مدیریت کاربران"
        if pending:
            lbl += f" 🔴{pending}"
        rows.append([{"text": lbl, "callback_data": "admin_users"}])
    if can("notify"):
        rows.append([{"text": "📢 اطلاع‌رسانی", "callback_data": "admin_notify"}])
    if can("care"):
        lbl = "💬 پشتیبانی و باشگاه"
        n = (b.get("tickets") or 0) + (b.get("rewards") or 0)
        if n:
            lbl += f" 🔴{n}"
        rows.append([{"text": lbl, "callback_data": "admin_care"}])
    if can("reports"):
        rows.append([{"text": "📊 گزارش‌ها", "callback_data": "admin_stats"}])
    if can("settings"):
        lbl = "⚙️ تنظیمات"
        if pending_pay:
            lbl += f" 🔴{pending_pay}"
        rows.append([{"text": lbl, "callback_data": "admin_settings"}])

    if not rows:
        rows.append([{"text": "🔒 هنوز دسترسی‌ای به شما داده نشده",
                      "callback_data": "noop"}])
    rows.append([{"text": "🔙 بازگشت", "callback_data": "back_main"}])
    return {"inline_keyboard": rows}


def kb_notify_menu(uid=None):
    """📢 اطلاع‌رسانی — جمع همه ابزارهای پیام‌رسانی"""
    def can(p):
        if uid is None:
            return True
        try:
            import permissions as _pm
            return _pm.has_perm(uid, p)
        except Exception:
            return True

    rows = []
    if can("bc_send"):
        rows.append([{"text": "📢 پیام همگانی", "callback_data": "admin_broadcast"}])
    if can("occasions"):
        rows.append([{"text": "🎂 مناسبت‌ها و تبریک", "callback_data": "oc_panel"}])
    if can("bc_event"):
        rows.append([{"text": "🎉 اطلاع‌رسانی رویداد", "callback_data": "ev_list"}])
    # 📣 فاز ۲۰ — پنل تبلیغات و کمپین
    if can("bc_send"):
        rows.append([{"text": "📣 تبلیغات و کمپین",
                      "callback_data": "ad_panel"}])
    rows.append([{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}])
    return {"inline_keyboard": rows}


def kb_care_menu(n_tickets=0, n_rewards=0, uid=None, n_inbox=0):
    """💬 پشتیبانی و باشگاه — تیکت + دستاورد + فروشگاه در یک جا"""
    def can(p):
        if uid is None:
            return True
        try:
            import permissions as _pm
            return _pm.has_perm(uid, p)
        except Exception:
            return True

    rows = []
    if can("tk_manage"):
        lbl = f"📱 تیکت‌های پشتیبانی ({n_tickets})" if n_tickets \
            else "📱 تیکت‌های پشتیبانی"
        rows.append([{"text": lbl, "callback_data": "tk_admin"}])
        # 📥 صندوق دریافت پیام‌های مستقیم
        ilbl = f"📥 صندوق دریافت 🔴{n_inbox}" if n_inbox else "📥 صندوق دریافت"
        rows.append([{"text": ilbl, "callback_data": "ib_list"}])
    if can("club_manage"):
        lbl = f"🏅 باشگاه و پاداش 🔴{n_rewards}" if n_rewards \
            else "🏅 باشگاه و پاداش"
        rows.append([{"text": lbl, "callback_data": "cl_panel"}])
    # ℹ️ فاز ۱۸-ج — تنظیمات «درباره ما و پشتیبانی» اینجا منتقل شد
    if can("sys_settings"):
        rows.append([{"text": "ℹ️ درباره ما و پشتیبانی",
                      "callback_data": "ab_admin"}])
    rows.append([{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}])
    return {"inline_keyboard": rows}


def kb_users_menu(stats=None, uid=None):
    """
    👥 منوی مدیریت کاربران — فاز ۱۳

    🎯 «درخواست‌های پروفایل هم بره تو مدیریت کاربران» ✅
       حالا اولین دکمه است (چون کار روزمره ادمین است).
    """
    st = stats or {}
    pend = st.get("pending") or 0

    def can(p):
        if uid is None:
            return True
        try:
            import permissions as _pm
            return _pm.has_perm(uid, p)
        except Exception:
            return True

    rows = []
    if uid is not None:
        try:
            import shared_api as _shared_api
            _identity = _shared_api.get_identity(uid)
            if (_identity.has_permission("us_approve")
                    or _identity.has_permission("receipt_approve")):
                rows.append([{"text": "📥 کارتابل پروفایل و فیش", "callback_data": "shared_inbox"}])
        except Exception:
            # Fail closed: a local SQLite role must not expose the shared inbox.
            pass
    # صندوق قدیمی SQLite با کارتابل مشترک جایگزین شده است.
    # 🧹 فاز ۳۹ — دو‌ستونی تا از سقف ۱۰ ردیف رد نشویم
    if can("us_view"):
        _r = [{"text": f"📋 کاربران ({st.get('total', 0)})",
               "callback_data": "um_list"},
              {"text": "🔍 جستجو", "callback_data": "u_search"}]
        rows.append(_r)
    if can("us_edit"):
        rows.append([{"text": "➕ افزودن کاربر دستی",
                      "callback_data": "um_add"}])
    io = []
    if can("us_import"):
        io.append({"text": "📥 ورودی گروهی", "callback_data": "admin_import"})
    if can("us_export"):
        io.append({"text": "📤 خروجی لیست", "callback_data": "admin_export"})
    if io:
        rows.append(io)
    if can("us_view"):
        rows.append([{"text": "🏷️ برچسب‌ها", "callback_data": "um_tags"},
                     {"text": "📊 گزارش کاربران", "callback_data": "um_report"}])
    if can("us_block"):
        rows.append([{"text": f"🚫 مسدودها ({st.get('blocked', 0)})",
                      "callback_data": "um_blocked"},
                     {"text": "📄 غیبت مجاز",
                      "callback_data": "ex_list"}])
    # 🏛️ فاز ۳۹ — مرکز صدور گواهینامه
    #    🎯 «مرکز صدور گواهی ببر تو قسمت کاربران، دکمشو بزار اونجا»
    if can("us_view"):
        rows.append([{"text": "🏛️ مرکز صدور گواهینامه",
                      "callback_data": "cc_home"}])
    # 👨‍💼 مدیریت ادمین‌ها — فقط سوپرادمین (SUPER_ONLY)
    if can("sys_settings"):
        rows.append([{"text": "⚙️ پارامترهای پروفایل",
                      "callback_data": "pf_params"}])
    if can("sys_admins"):
        rows.append([{"text": f"👨‍💼 مدیریت ادمین‌ها ({st.get('admins', 0)})",
                      "callback_data": "um_admins"}])
    rows.append([{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}])
    return {"inline_keyboard": rows}


def kb_payment_methods(current=None):
    """
    💳 روش‌های پرداخت — فاز ۱۳: ۶ روش

    ⚠️ منبع حقیقت payments.PAYMENT_METHODS است؛ اینجا فقط
       برای سازگاری با فراخوانی‌های قدیمی نگه داشته شده.
    """
    def mark(v):
        return "✅ " if current == v else ""
    rows = [
        ("none", "❌ غیرفعال (رایگان)"),
        ("card", "💳 کارت به کارت"),
        ("bale_wallet", "🏦 درگاه پرداخت بله (کیف پول)"),
        ("custom_gateway", "🔗 درگاه پرداخت سفارشی"),
        ("onsite", "💰 پرداخت در محل"),
        ("points", "🏆 پرداخت با امتیاز"),
        ("multi", "🎛️ چند روشی (انتخاب کاربر)"),
    ]
    return {"inline_keyboard": [
        [{"text": f"{mark(k)}{lbl}", "callback_data": f"paym_{k}"}]
        for k, lbl in rows]}


def kb_settings(uid=None, pending_pay=0):
    """
    ⚙️ تنظیمات — فاز ۱۳

    💰 «مالی و تراکنش» زیرمجموعه «روش‌های پرداخت» شد
       و کل بخش پرداخت فقط برای سوپرادمین دیده می‌شود.
    """
    def can(p):
        if uid is None:
            return True
        try:
            import permissions as _pm
            return _pm.has_perm(uid, p)
        except Exception:
            return True

    rows = []
    if can("sys_settings"):
        rows.append([{"text": "📝 مدیریت متن‌ها", "callback_data": "set_texts"}])
    # 💳 پرداخت + مالی — SUPER_ONLY
    if can("fin_settings") or can("fin_view"):
        lbl = "💳 پرداخت و مالی"
        if pending_pay:
            lbl += f" 🔴{pending_pay}"
        rows.append([{"text": lbl, "callback_data": "set_payment"}])
    if can("sys_settings"):
        rows += [
            [{"text": "🔗 عضویت اجباری", "callback_data": "admin_force_join"}],
            [{"text": "📱 تنظیمات OTP سفیر", "callback_data": "set_otp"}],
            [{"text": "🎓 گواهینامه و بلیط",
              "callback_data": "ct_hub"}],
        ]
    if can("sys_points"):
        rows.append([{"text": "🏅 قوانین امتیاز", "callback_data": "pr_list"}])
    if can("sys_backup"):
        rows.append([{"text": "💾 بک‌آپ دیتابیس", "callback_data": "admin_backup"},
                     {"text": "🗄️ دیتابیس", "callback_data": "admin_dbinfo"}])
    rows.append([{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}])
    return {"inline_keyboard": rows}


def kb_payment_settings(pending_rcp=0, uid=None):
    """
    💳 پرداخت و مالی — فاز ۱۳

    🎯 «مالی تراکنش هم بره تو تنظیمات روش های پرداخت هم زیر مجموعش بشه»
       همه چیز پول اینجاست: کارت، درگاه، تراکنش، درآمد، رسید، متن، تست.
    """
    # 🎯 فاز ۲۴: «منو مالی پرداخت هم جامع کن که بهم ریخته نباشه»
    #    قبلاً ۱۲ دکمهٔ هم‌ارز پشت هم بود. حالا سه گروه روشن:
    #       💰 پول کجاست  ·  🏦 راه‌های دریافت  ·  ⚙️ تنظیمات
    rows = []
    if pending_rcp:
        rows.append([{"text": f"🧾 رسیدهای در انتظار ({pending_rcp})",
                      "callback_data": "pay_receipts"}])
    rows += [
        [{"text": "━━━  💰 گزارش مالی  ━━━",
          "callback_data": "noop"}],
        [{"text": "📊 داشبورد درآمد", "callback_data": "fin_dash"},
         {"text": "🧾 تراکنش‌ها", "callback_data": "fin_tx_0_all"}],

        [{"text": "━━━  🏦 راه‌های دریافت  ━━━",
          "callback_data": "noop"}],
        [{"text": "💳 کارت‌های بانکی", "callback_data": "pay_cards"},
         {"text": "🏦 کیف پول بله", "callback_data": "pay_wallet"}],
        [{"text": "🔗 درگاه‌های سفارشی", "callback_data": "pay_gateways"}],
        [{"text": "🔗 لینک پرداخت غیرمتمرکز",
          "callback_data": "pl_panel"}],
        [{"text": "💠 پرداخت مرحله‌ای (اقساط · جلسه‌ای)",
          "callback_data": "pp_panel"}],

        [{"text": "━━━  ⚙️ تنظیمات  ━━━", "callback_data": "noop"}],
        [{"text": "🧱 هزینه زیرساخت و خدمات",
          "callback_data": "pay_infra"}],
        [{"text": "💳 کارمزد درگاه‌ها", "callback_data": "pay_fee"},
         {"text": "🛡️ هشدار فیلترشکن", "callback_data": "pay_vpn"}],
        [{"text": "🎛️ روش‌های پرداخت", "callback_data": "pay_adv"}],
        [{"text": "📝 متن‌های پرداخت", "callback_data": "pay_texts"},
         {"text": "🧪 تست پرداخت", "callback_data": "pay_test"}],

        [{"text": "🔙 تنظیمات", "callback_data": "admin_settings"}],
    ]
    return {"inline_keyboard": rows}
