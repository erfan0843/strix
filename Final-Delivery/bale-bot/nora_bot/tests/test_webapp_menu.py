"""Keep the classic chat menus and add the existing web app as an optional Bale Mini App entry."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bale_api
import config


CLASSIC_USER_BUTTONS = {
    "🎉 رویدادها", "📝 فرم‌ها", "👤 پروفایل من", "✋ حضور و غیاب",
    "👥 دعوت از دوستان", "🔔 اعلان‌ها", "💬 پشتیبانی", "🏠 منوی اصلی",
}


def _buttons(markup):
    return [button for row in markup["keyboard"] for button in row]


class WebAppMenuTests(unittest.TestCase):
    def test_existing_site_url_requires_a_public_https_address(self):
        self.assertTrue(config.is_valid_webapp_url("https://nora.example.ir"))
        self.assertTrue(config.is_valid_webapp_url("https://nora.example.ir/app"))
        self.assertFalse(config.is_valid_webapp_url("http://nora.example.ir"))
        self.assertFalse(config.is_valid_webapp_url("https://user:pass@nora.example.ir"))
        self.assertFalse(config.is_valid_webapp_url("https://nora.example.ir/path?token=secret"))
        self.assertFalse(config.is_valid_webapp_url("https://localhost"))

    def test_classic_user_keyboard_stays_intact_without_a_webapp_url(self):
        with patch.object(bale_api, "NORA_WEBAPP_URL", ""):
            markup = bale_api.kb_persistent(is_admin=False)
        buttons = _buttons(markup)
        labels = {button["text"] for button in buttons}

        self.assertTrue(CLASSIC_USER_BUTTONS <= labels)
        self.assertTrue(all("web_app" not in button for button in buttons))
        self.assertIs(markup["is_persistent"], True)

    def test_webapp_button_opens_the_same_configured_domain_and_keeps_classic_menu(self):
        site_url = "https://nora.example.ir"
        with patch.object(bale_api, "NORA_WEBAPP_URL", site_url):
            user_markup = bale_api.kb_persistent(is_admin=False)
            staff_markup = bale_api.kb_persistent(is_admin=True, is_full=False)
            admin_markup = bale_api.kb_persistent(is_admin=True, is_full=True)

        staff_buttons = _buttons(staff_markup)
        staff_labels = {button["text"] for button in staff_buttons}
        self.assertTrue(CLASSIC_USER_BUTTONS <= staff_labels)
        self.assertIn(bale_api.BTN_ADMIN, staff_labels)
        self.assertIn(bale_api.BTN_WEBAPP, staff_labels)

        user_buttons = _buttons(user_markup)
        launch = next(button for button in user_buttons if button["text"] == bale_api.BTN_WEBAPP)
        self.assertEqual(launch["web_app"], {"url": site_url})
        self.assertTrue(CLASSIC_USER_BUTTONS <= {button["text"] for button in user_buttons})

        admin_buttons = _buttons(admin_markup)
        admin_launch = next(button for button in admin_buttons if button["text"] == bale_api.BTN_WEBAPP)
        self.assertEqual(admin_launch["web_app"], {"url": site_url})
        admin_labels = {button["text"] for button in admin_buttons}
        self.assertIn("👨‍💼 پنل ادمین", admin_labels)
        self.assertIn("👤 نمای کاربر", admin_labels)


if __name__ == "__main__":
    unittest.main(verbosity=2)
