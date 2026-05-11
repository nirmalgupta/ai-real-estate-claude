"""Configuration-shape tests for TelegramChannel (no network)."""
import unittest

from pipeline.deliver.telegram import TelegramChannel


class TelegramConfigTests(unittest.TestCase):
    def setUp(self):
        self.ch = TelegramChannel()

    def test_full_config(self):
        self.assertTrue(self.ch.is_configured(
            {"bot_token": "1234:abc", "chat_id": "5555"}
        ))

    def test_missing_bot_token(self):
        self.assertFalse(self.ch.is_configured({"chat_id": "5555"}))

    def test_missing_chat_id(self):
        self.assertFalse(self.ch.is_configured({"bot_token": "1234:abc"}))

    def test_blank_strings_disable(self):
        self.assertFalse(self.ch.is_configured(
            {"bot_token": " ", "chat_id": "5555"}
        ))


if __name__ == "__main__":
    unittest.main()
