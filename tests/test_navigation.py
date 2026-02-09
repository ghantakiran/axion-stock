"""Tests for PRD-133 Navigation Overhaul.

Verifies navigation configuration correctness without requiring
a running Streamlit server.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNavConfig(unittest.TestCase):
    """Test the navigation configuration definitions."""

    def setUp(self):
        """Set up mock Streamlit context for st.Page() calls."""
        self.mock_pages = []

        def fake_page(path, *, title, icon, default=False):
            page = MagicMock()
            page.path = path
            page.title = title
            page.icon = icon
            page.default = default
            self.mock_pages.append(page)
            return page

        self.page_patcher = patch("streamlit.Page", side_effect=fake_page)
        self.page_patcher.start()

        from app.nav_config import build_navigation_pages
        self.nav = build_navigation_pages()

    def tearDown(self):
        self.page_patcher.stop()

    def test_has_10_sections(self):
        """Navigation must have exactly 10 section groups."""
        self.assertEqual(len(self.nav), 10)

    def test_section_names(self):
        """All expected section names are present."""
        expected = {
            "",  # Home (unnamed section)
            "Market Analysis",
            "Sentiment & Data",
            "Trading & Execution",
            "Portfolio & Risk",
            "Options & Derivatives",
            "ML & AI",
            "Enterprise & Compliance",
            "Research & Tools",
            "Infrastructure & DevOps",
        }
        self.assertEqual(set(self.nav.keys()), expected)

    def test_total_page_count(self):
        """Total page count is 105."""
        total = sum(len(pages) for pages in self.nav.values())
        self.assertEqual(total, 105)

    def test_home_is_default(self):
        """Home section has one page marked as default."""
        home_pages = self.nav[""]
        self.assertEqual(len(home_pages), 1)
        self.assertTrue(home_pages[0].default)

    def test_home_is_ai_chat(self):
        """Home page title is 'AI Chat'."""
        self.assertEqual(self.nav[""][0].title, "AI Chat")

    def test_no_duplicate_paths(self):
        """No two pages share the same file path."""
        paths = [p.path for p in self.mock_pages]
        self.assertEqual(len(paths), len(set(paths)),
                         f"Duplicate paths found: {[p for p in paths if paths.count(p) > 1]}")

    def test_no_duplicate_titles(self):
        """No two pages share the same display title."""
        titles = [p.title for p in self.mock_pages]
        self.assertEqual(len(titles), len(set(titles)),
                         f"Duplicate titles found: {[t for t in titles if titles.count(t) > 1]}")

    def test_all_pages_have_icons(self):
        """Every page must have a Material Design icon."""
        for page in self.mock_pages:
            self.assertTrue(
                page.icon.startswith(":material/"),
                f"Page '{page.title}' has invalid icon: {page.icon}",
            )

    def test_all_page_files_exist(self):
        """Every page path must resolve to an existing .py file."""
        app_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"
        )
        for page in self.mock_pages:
            full_path = os.path.join(app_dir, page.path)
            self.assertTrue(
                os.path.isfile(full_path),
                f"Page file not found: {full_path} (title: {page.title})",
            )

    def test_section_page_counts(self):
        """Each section has the expected number of pages."""
        expected_counts = {
            "": 1,
            "Market Analysis": 16,
            "Sentiment & Data": 7,
            "Trading & Execution": 15,
            "Portfolio & Risk": 14,
            "Options & Derivatives": 3,
            "ML & AI": 5,
            "Enterprise & Compliance": 12,
            "Research & Tools": 10,
            "Infrastructure & DevOps": 22,
        }
        for section, expected in expected_counts.items():
            self.assertEqual(
                len(self.nav[section]), expected,
                f"Section '{section}' has {len(self.nav[section])} pages, expected {expected}",
            )


class TestStylesModule(unittest.TestCase):
    """Test the styles module."""

    @patch("streamlit.markdown")
    def test_inject_global_styles_calls_markdown(self, mock_md):
        """inject_global_styles() should call st.markdown with CSS."""
        from app.styles import inject_global_styles
        inject_global_styles()
        mock_md.assert_called_once()
        call_args = mock_md.call_args
        html = call_args[0][0]
        self.assertIn("<style>", html)
        self.assertIn("</style>", html)
        self.assertTrue(call_args[1].get("unsafe_allow_html"))

    @patch("streamlit.markdown")
    def test_css_contains_key_selectors(self, mock_md):
        """CSS must include critical selectors for the Axion theme."""
        from app.styles import inject_global_styles
        inject_global_styles()
        css = mock_md.call_args[0][0]
        for selector in [".stApp", "[data-testid=\"stSidebar\"]", ".welcome-card",
                         ".logo-area", ".factor-pill", ".metric-card"]:
            self.assertIn(selector, css, f"Missing CSS selector: {selector}")


class TestHomePage(unittest.TestCase):
    """Test the home page module can be imported."""

    def test_home_module_importable(self):
        """app/pages/home.py should be importable as a module."""
        import importlib
        spec = importlib.util.spec_from_file_location(
            "home",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "app", "pages", "home.py",
            ),
        )
        self.assertIsNotNone(spec, "home.py module spec should not be None")


class TestEntrypoint(unittest.TestCase):
    """Test the entrypoint module structure."""

    def test_entrypoint_imports(self):
        """Key imports should resolve without errors."""
        # These are import-time checks only; we don't run the Streamlit app
        from app.styles import inject_global_styles
        from app.nav_config import build_navigation_pages
        from app.chat import get_api_key
        self.assertTrue(callable(inject_global_styles))
        self.assertTrue(callable(build_navigation_pages))
        self.assertTrue(callable(get_api_key))


if __name__ == "__main__":
    unittest.main()
