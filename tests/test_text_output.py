import unittest

from career_radar.text_output import escape_markdown


class TextOutputTests(unittest.TestCase):
    def test_markdown_escaping_removes_controls_and_escapes_metacharacters(self) -> None:
        value = "safe\n\x7f\\`*_{}[]()#!|<>"

        escaped = escape_markdown(value)

        self.assertEqual(escaped, r"safe\\\`\*\_\{\}\[\]\(\)\#\!\|\<\>")


if __name__ == "__main__":
    unittest.main()
