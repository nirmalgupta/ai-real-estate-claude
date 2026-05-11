"""Logic tests for the delivery registry (no AppleScript / no network)."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.deliver import Channel, SendResult, enabled_channels, send


class _FakeChannel(Channel):
    """Test double — captures calls instead of doing real work."""
    name = "_fake"
    max_bytes = 1024  # 1KB ceiling for tests

    def __init__(self):
        self.calls: list[tuple[Path, str, dict]] = []

    def is_configured(self, config: dict) -> bool:
        return "token" in config

    def send(self, pdf_path, body, config):
        self.calls.append((pdf_path, body, config))
        return SendResult(ok=True, note=f"fake-sent to {config['token']}")


class DeliveryRegistryTests(unittest.TestCase):
    def setUp(self):
        # Register a fresh fake channel without disturbing the real registry
        import pipeline.deliver as deliver_mod
        self.deliver_mod = deliver_mod
        self.fake = _FakeChannel()
        deliver_mod._REGISTRY["_fake"] = self.fake

    def tearDown(self):
        self.deliver_mod._REGISTRY.pop("_fake", None)

    def _make_tmp_pdf(self, size: int) -> Path:
        d = TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "test.pdf"
        p.write_bytes(b"x" * size)
        return p

    def test_enabled_channels_reads_config(self):
        cfg = {"channels": {"_fake": {"token": "abc"}}}
        self.assertIn("_fake", enabled_channels(cfg))

    def test_enabled_channels_omits_empty(self):
        cfg = {"channels": {"_fake": {}}}
        self.assertNotIn("_fake", enabled_channels(cfg))

    def test_send_routes_to_channel(self):
        cfg = {"channels": {"_fake": {"token": "xyz"}}}
        pdf = self._make_tmp_pdf(100)
        result = send("_fake", pdf, "hi", config=cfg)
        self.assertTrue(result.ok)
        self.assertIn("xyz", result.note)
        self.assertEqual(len(self.fake.calls), 1)

    def test_send_skips_unconfigured(self):
        cfg = {"channels": {}}
        pdf = self._make_tmp_pdf(100)
        result = send("_fake", pdf, "hi", config=cfg)
        self.assertFalse(result.ok)
        self.assertTrue(result.skipped)

    def test_send_rejects_oversized(self):
        cfg = {"channels": {"_fake": {"token": "abc"}}}
        # 2KB > 1KB channel ceiling
        pdf = self._make_tmp_pdf(2048)
        result = send("_fake", pdf, "hi", config=cfg)
        self.assertFalse(result.ok)
        self.assertIn("too large", result.note)
        self.assertEqual(len(self.fake.calls), 0)

    def test_send_unknown_channel(self):
        cfg = {"channels": {"_fake": {"token": "abc"}}}
        pdf = self._make_tmp_pdf(100)
        result = send("nope", pdf, "hi", config=cfg)
        self.assertFalse(result.ok)
        self.assertIn("unknown channel", result.note)


class ImessageStubTests(unittest.TestCase):
    """ImessageChannel.is_configured should not require osascript."""

    def test_is_configured_phone_number(self):
        from pipeline.deliver.imessage import ImessageChannel
        ch = ImessageChannel()
        self.assertTrue(ch.is_configured({"to": "+15551234567"}))

    def test_is_configured_empty(self):
        from pipeline.deliver.imessage import ImessageChannel
        ch = ImessageChannel()
        self.assertFalse(ch.is_configured({}))
        self.assertFalse(ch.is_configured({"to": ""}))


if __name__ == "__main__":
    unittest.main()
