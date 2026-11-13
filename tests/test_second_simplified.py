import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from modules.second_simplified import to_second_simplified

ROOT = Path(__file__).resolve().parents[1]


class SecondSimplifiedTests(unittest.TestCase):
    def test_locale_is_complete_and_matches_the_draft_converter(self):
        source = json.loads((ROOT / "locales/zh-CN.json").read_text(encoding="utf-8"))
        target = json.loads((ROOT / "locales/zh-2jian.json").read_text(encoding="utf-8"))
        self.assertEqual(target.keys(), source.keys())
        expected = {key: to_second_simplified(value) for key, value in source.items()}
        expected["meta.description"] = to_second_simplified(
            "基于1977年第二次汉字简化方案（草案）的日语学习助手界面。"
        )
        self.assertEqual(
            target,
            expected,
            "The historical locale is generated from every Simplified Chinese string.",
        )
        self.assertEqual(target["theme.switch_colour"], "切换色采主题")
        self.assertIn("1977", target["meta.description"])

    def test_google_translation_uses_simplified_chinese_then_applies_draft_forms(self):
        import services

        payload = json.dumps([[["答复", "reply", None, None]]]).encode()
        response = io.BytesIO(payload)
        service = services.MachineTranslationService
        service.cache.pop(("zh-2jian", "reply"), None)
        with patch.object(service, "providers", return_value=["google"]), patch.object(
            services, "urlopen", return_value=response
        ) as open_url:
            translation = service.meaning("reply", "zh-2jian")
        self.assertEqual(translation, "荅复")
        query = parse_qs(urlparse(open_url.call_args.args[0]).query)
        self.assertEqual(query["tl"], ["zh-CN"])

    def test_language_api_serves_new_locale(self):
        import app

        with patch.object(app, "access_hash", return_value="a" * 64), patch.object(
            app.request_log, "record"
        ), patch.object(app.user_data, "new_code", return_value="ABC123"), app.app.test_client() as client:
            with client.session_transaction() as session:
                session["authenticated"] = True
            response = client.get("/api/locales/zh-2jian")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["translations"]["theme.switch_colour"], "切换色采主题")


if __name__ == "__main__":
    unittest.main()
