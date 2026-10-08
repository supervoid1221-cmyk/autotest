from unittest import TestCase
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from fullstack_framework.commons.ui_executor import (
    _cached_chromedriver,
    _capture_step_screenshot,
    _create_driver,
)
from case_ui.browser_token import should_inject_environment_auth


class EnvironmentAuthScopeTests(TestCase):
    def test_relative_navigation_uses_environment_auth(self):
        self.assertTrue(should_inject_environment_auth("https://api.example.com", ["/login"]))

    def test_same_origin_absolute_navigation_uses_environment_auth(self):
        self.assertTrue(
            should_inject_environment_auth(
                "https://api.example.com/base", ["https://api.example.com/login"]
            )
        )

    def test_external_absolute_navigation_skips_environment_auth(self):
        self.assertFalse(
            should_inject_environment_auth(
                "https://api-test.helix.city", ["https://www.oishare.com/tools/cpf.html"]
            )
        )

    def test_no_navigation_skips_environment_auth(self):
        self.assertFalse(should_inject_environment_auth("https://api.example.com", []))


class ChromeRunModeTests(TestCase):
    @patch("fullstack_framework.commons.ui_executor._resolve_chromedriver")
    @patch("fullstack_framework.commons.ui_executor.webdriver.Chrome")
    def test_headless_mode_adds_headless_argument(self, chrome, resolve):
        resolve.return_value = (Path("/tmp/chromedriver"), "测试")
        _create_driver("chrome", "headless")

        options = chrome.call_args.kwargs["options"]
        self.assertIn("--headless=new", options.arguments)

    @patch("fullstack_framework.commons.ui_executor._resolve_chromedriver")
    @patch("fullstack_framework.commons.ui_executor.webdriver.Chrome")
    def test_headed_mode_does_not_add_headless_argument(self, chrome, resolve):
        resolve.return_value = (Path("/tmp/chromedriver"), "测试")
        _create_driver("chrome", "headed")

        options = chrome.call_args.kwargs["options"]
        self.assertNotIn("--headless=new", options.arguments)
        self.assertIn("--window-size=1920,1080", options.arguments)

    def test_unknown_run_mode_fails_before_starting_browser(self):
        with self.assertRaisesRegex(ValueError, "不支持的浏览器运行模式"):
            _create_driver("chrome", "unknown")


class ChromeDriverCacheTests(TestCase):
    def test_selects_highest_matching_chrome_major_from_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_driver = root / "chromedriver/mac-x64/151.0.7922.120/chromedriver"
            newest_driver = root / "chromedriver/mac-x64/151.0.7922.138/chromedriver"
            other_driver = root / "chromedriver/mac-x64/149.0.7827.155/chromedriver"
            for driver in (old_driver, newest_driver, other_driver):
                driver.parent.mkdir(parents=True, exist_ok=True)
                driver.touch(mode=0o755)
                driver.chmod(0o755)

            self.assertEqual(_cached_chromedriver("151", root), newest_driver)


class SeleniumScreenshotTests(TestCase):
    def test_capture_step_screenshot_returns_relative_report_path(self):
        driver = Mock()
        driver.save_screenshot.return_value = True

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "fullstack_framework.commons.ui_executor.Path.cwd", return_value=Path(temp_dir)
        ):
            screenshot_path = _capture_step_screenshot(driver, 12, 34, "passed")

        self.assertTrue(screenshot_path.startswith("screenshots/selenium_passed_12_34_"))
        self.assertTrue(screenshot_path.endswith(".png"))
        driver.save_screenshot.assert_called_once()

    def test_capture_step_screenshot_failure_does_not_raise(self):
        driver = Mock()
        driver.save_screenshot.side_effect = RuntimeError("capture failed")

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "fullstack_framework.commons.ui_executor.Path.cwd", return_value=Path(temp_dir)
        ):
            self.assertEqual(_capture_step_screenshot(driver, 12, 34, "failed"), "")
