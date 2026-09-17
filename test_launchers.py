"""Portable launcher checks; run only generated scripts, never the importer."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class LauncherTests(unittest.TestCase):
    def test_import_launcher_uses_own_venv_and_preserves_exit_code(self):
        launcher = ROOT / 'Import Session.cmd'
        self.assertTrue(launcher.is_file(), 'The launcher named by the app must exist')
        text = launcher.read_text()
        self.assertIn('cd /d "%~dp0"', text)
        self.assertIn('".venv\\Scripts\\python.exe" ig_session_import.py', text)
        if os.name != 'nt':
            return
        with tempfile.TemporaryDirectory(prefix='offline launcher ') as directory:
            directory = Path(directory)
            shutil.copyfile(launcher, directory / launcher.name)
            cmd = os.environ.get('COMSPEC', 'cmd.exe')
            # Exercise missing environment without ever reaching a hidden prompt.
            result = subprocess.run([cmd, '/d', '/c', str(directory / launcher.name)],
                                    input='\n', capture_output=True, text=True, timeout=20,
                                    cwd=directory.parent)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('Setup InstaVoice.cmd', result.stdout)
            subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(directory / '.venv')],
                           check=True, capture_output=True, timeout=60)
            # Not the real importer: generated fixture cannot log in or send.
            (directory / 'ig_session_import.py').write_text(
                "import sys\nprint('OFFLINE_IMPORT_LAUNCH_OK')\nraise SystemExit(7)\n")
            result = subprocess.run([cmd, '/d', '/c', str(directory / launcher.name)],
                                    input='\n', capture_output=True, text=True, timeout=20,
                                    cwd=directory.parent)
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
            self.assertIn('OFFLINE_IMPORT_LAUNCH_OK', result.stdout)

    def test_setup_checks_python_311_before_venv_and_has_py_fallback(self):
        text = (ROOT / 'Setup InstaVoice.cmd').read_text()
        self.assertIn('sys.version_info[:2] != (3, 11)', text)
        self.assertIn('py -3.11', text)
        self.assertIn('Python 3.11', text)
        self.assertIn('".venv\\Scripts\\python.exe" -c', text)
        self.assertIn('cd /d "%~dp0"', text)


if __name__ == '__main__':
    unittest.main()
