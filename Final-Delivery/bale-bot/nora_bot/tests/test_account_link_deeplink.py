"""پیوند حساب: پارامتر start ربات واقعاً کاربر را به صفحهٔ حساب در بله می‌برد.

این آزمون رفتار واقعی ماژول را می‌سنجد (بدون هیچ تماس شبکه‌ای) و در پایان
سیم‌کشی مسیر `?start=link_account` در main.py را به‌صورت ایستا بررسی می‌کند تا
دکمهٔ «بازکردن بله» در صفحهٔ حساب دوباره به مسیری بی‌پاسخ برنگردد.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import account_link  # noqa: E402


def _buttons(markup):
    return [button for row in markup["inline_keyboard"] for button in row]


class AccountLinkDeepLinkTests(unittest.TestCase):
    def _sent(self, base, uid=73421, cid=555):
        """send را جایگزین می‌کند تا پیام و دکمهٔ ساخته‌شده ثبت شود."""
        calls = []

        def fake_send(chat_id, text, kb=None, reply_to=None):
            calls.append({"cid": chat_id, "text": text, "kb": kb})
            return {"ok": True}

        with patch.object(account_link, "send", fake_send), \
                patch.object(account_link, "NORA_WEBAPP_URL", base):
            account_link.start(cid, uid)
        return calls[0]

    def test_configured_webapp_opens_the_account_page_in_link_mode(self):
        """نشانهٔ صریح مسیر پیوند باید در نشانی باشد؛ وگرنه صفحه ورود خودکار می‌زند
        و امضای یک‌بارمصرفِ لازم برای اثبات مالکیت همان‌جا خرج می‌شود."""
        sent = self._sent("https://nora.example.ir")
        self.assertEqual(account_link.account_webapp_url("https://nora.example.ir"),
                         "https://nora.example.ir/account.html?link=bale")
        buttons = _buttons(sent["kb"])
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0]["web_app"]["url"],
                         "https://nora.example.ir/account.html?link=bale")
        self.assertNotIn("callback_data", buttons[0])
        self.assertTrue("بله" in sent["text"])

    def test_trailing_slash_does_not_duplicate(self):
        sent = self._sent("https://nora.example.ir/")
        self.assertEqual(_buttons(sent["kb"])[0]["web_app"]["url"],
                         "https://nora.example.ir/account.html?link=bale")

    def test_link_url_carries_no_signature_or_identifier(self):
        """امضای بله و هیچ شناسهٔ کاربری در نشانی نمی‌آید؛ امضا داخل مینی‌اپ ساخته می‌شود."""
        sent = self._sent("https://nora.example.ir", uid=987654321)
        url = _buttons(sent["kb"])[0]["web_app"]["url"]
        self.assertNotIn("987654321", url)
        self.assertNotIn("hash=", url)
        self.assertNotIn("auth_date", url)
        self.assertTrue(url.endswith("?link=bale"))

    def test_message_carries_no_signature_material(self):
        """متن پیام هم هیچ دادهٔ امضاشده‌ای ندارد؛ فقط راهنمای ورود به وب‌اپ است."""
        sent = self._sent("https://nora.example.ir", uid=987654321)
        self.assertNotIn("init_data", sent["text"])
        self.assertNotIn("hash=", sent["text"])

    def test_without_webapp_url_the_user_is_told_instead_of_a_dead_button(self):
        sent = self._sent("")
        self.assertIsNone(sent["kb"])
        self.assertEqual(account_link.account_webapp_url(""), "")
        self.assertTrue("تنظیم نشده" in sent["text"])

    def test_start_route_is_wired_in_the_bot(self):
        """بررسی ایستا: مسیر start به همین ماژول وصل است و قبل از کد معرف می‌آید."""
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('if param == "link_account":', main)
        self.assertIn("return account_link_mod.start(cid, uid, user)", main)
        self.assertIn("import account_link as account_link_mod", main)
        link_at = main.index('if param == "link_account":')
        referral_at = main.index("SELECT bale_user_id, first_name FROM users WHERE referral_code=?")
        self.assertLess(link_at, referral_at,
                        "پارامتر link_account نباید به‌عنوان کد معرف جست‌وجو شود")


if __name__ == "__main__":
    unittest.main(verbosity=2)
