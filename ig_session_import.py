"""Manually import your own existing web session using a local hidden prompt.

The session is sent to Instagram for validation and stored in plaintext locally.
Never paste it into chat, logs, screenshots, source control, or issue reports.
"""
import getpass
import sys
import warnings
from pathlib import Path

from safe_client import SafeClient as Client

SESSION_FILE = Path(__file__).resolve().parent / 'ig_session.json'


def main():
    print('WARNING: ig_session.json stores your account session in plaintext.')
    print('Protect this file like a password. Never share or commit it.')
    print("In your logged-in browser: Instagram -> F12 -> Application -> Cookies -> sessionid")
    try:
        # Never fall back to an echoed prompt on unsupported consoles.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            token = getpass.getpass('sessionid (hidden): ').strip()
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        print('\nHidden input unavailable or cancelled. Run Import Session.cmd in a terminal.')
        return 1
    if not token:
        print('Nothing entered. Aborted.')
        return 1

    try:
        cl = Client()
        cl.delay_range = [2, 6]
        if not cl.login_by_sessionid(token):
            raise ValueError('Session not accepted')
        cl.dump_settings(SESSION_FILE)
    except Exception:
        # Library exception text/logging can contain the cookie or request headers.
        print('IMPORT_FAILED. Session validation or local storage failed.')
        print('Check the cookie and folder permissions; no automatic retry.')
        return 2
    finally:
        token = None

    print('Session saved to ig_session.json. Connect it explicitly in the desktop app.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
