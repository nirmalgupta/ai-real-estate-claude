"""Configuration-shape tests for SlackChannel (no network)."""
import unittest

from pipeline.deliver.slack import SlackChannel


class SlackConfigTests(unittest.TestCase):
    def setUp(self):
        self.ch = SlackChannel()

    def test_full_config(self):
        self.assertTrue(self.ch.is_configured(
            {"bot_token": "xoxb-abc", "channel": "C123456"}
        ))

    def test_missing_token(self):
        self.assertFalse(self.ch.is_configured({"channel": "C123456"}))

    def test_missing_channel(self):
        self.assertFalse(self.ch.is_configured({"bot_token": "xoxb-abc"}))

    def test_blank_values(self):
        self.assertFalse(self.ch.is_configured(
            {"bot_token": "", "channel": "C123456"}
        ))


if __name__ == "__main__":
    unittest.main()
