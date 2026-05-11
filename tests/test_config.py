"""Tests for the shared user-config loader."""
import os
import unittest
from unittest import mock

from pipeline.common import config


class ApiKeyTests(unittest.TestCase):
    def test_env_var_wins(self):
        with mock.patch.dict(os.environ, {"HUD_API_KEY": "from-env"}):
            with mock.patch.object(
                config, "load",
                return_value={"apis": {"hud": {"key": "from-file"}}},
            ):
                self.assertEqual(config.api_key("hud", env_var="HUD_API_KEY"),
                                 "from-env")

    def test_file_used_when_env_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(
                config, "load",
                return_value={"apis": {"bea": {"key": "from-file"}}},
            ):
                self.assertEqual(config.api_key("bea", env_var="BEA_API_KEY"),
                                 "from-file")

    def test_derived_env_var(self):
        """No explicit env_var, but FOO_API_KEY is set in env."""
        with mock.patch.dict(os.environ, {"NEW_API_KEY": "auto"},
                             clear=True):
            with mock.patch.object(config, "load", return_value={}):
                self.assertEqual(config.api_key("new"), "auto")

    def test_no_key_anywhere_returns_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(config, "load", return_value={}):
                self.assertIsNone(config.api_key("hud", env_var="HUD_API_KEY"))

    def test_blank_file_value_returns_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(
                config, "load",
                return_value={"apis": {"hud": {"key": "   "}}},
            ):
                self.assertIsNone(config.api_key("hud", env_var="HUD_API_KEY"))


if __name__ == "__main__":
    unittest.main()
