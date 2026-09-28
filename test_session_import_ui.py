"""Offline regression checks for the in-app session import panel in ui/app.js.

render() runs on every background status poll, so clearing the token field from
render() erased a freshly pasted sessionid within a frame and the import could
never be submitted. The field must only clear when the panel closes.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_JS = ROOT / 'ui' / 'app.js'

CLEAR_TOKEN = "$('sessionImportInput').value=''"


def body(source, header):
    """Return the brace-balanced source of the function introduced by header."""
    start = source.index(header)
    depth = 0
    for index in range(source.index('{', start), len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f'Unbalanced braces after {header!r}')


class SessionImportUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_JS.read_text(encoding='utf-8')

    def test_render_does_not_clear_the_session_token(self):
        render = body(self.source, 'function render()')
        self.assertNotIn(CLEAR_TOKEN, render,
                         'render() runs on every status poll and must not clear the pasted sessionid')

    def test_closing_the_panel_clears_the_token(self):
        cancel = body(self.source, 'function cancelSessionImport(')
        self.assertIn(CLEAR_TOKEN, cancel,
                      'The field must clear when the panel closes, as the panel help text promises')

    def test_import_button_stays_disabled_until_a_token_is_typed(self):
        render = body(self.source, 'function render()')
        self.assertIn("$('confirmSessionImport').disabled=!state.sessionImport || "
                      "!$('sessionImportInput').value.trim()", render,
                      'An empty token must not offer a click that silently does nothing')

    def test_typing_refreshes_the_import_button(self):
        self.assertIn("$('sessionImportInput').addEventListener('input',render)", self.source,
                      'Typing must re-render so the import button enables')

    def test_confirm_reads_the_token_before_the_panel_clears_it(self):
        confirm = body(self.source, "$('confirmSessionImport').addEventListener('click'")
        read = confirm.index("const token=$('sessionImportInput').value.trim()")
        cancel = confirm.index('cancelSessionImport()', read)
        call = confirm.index("call('import_session',token)", cancel)
        self.assertLess(read, cancel, 'Capture the token before the panel clears the field')
        self.assertLess(cancel, call, 'Send the captured token after clearing the field')


if __name__ == '__main__':
    unittest.main()
