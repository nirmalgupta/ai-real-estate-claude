"""Configuration-shape tests for EmailChannel (no SMTP)."""
import unittest

from pipeline.deliver.email import EmailChannel


class EmailIsConfiguredTests(unittest.TestCase):
    def setUp(self):
        self.ch = EmailChannel()
        self.full = {
            "to": "a@b.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "secret",
        }

    def test_full_config_is_configured(self):
        self.assertTrue(self.ch.is_configured(self.full))

    def test_missing_any_required_disables(self):
        for k in EmailChannel.REQUIRED:
            cfg = dict(self.full)
            cfg[k] = ""
            self.assertFalse(self.ch.is_configured(cfg),
                             f"{k} blank should disable")

    def test_unknown_extras_ignored(self):
        cfg = dict(self.full)
        cfg["whatever"] = "x"
        self.assertTrue(self.ch.is_configured(cfg))


if __name__ == "__main__":
    unittest.main()
