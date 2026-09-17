"""Instagram sending backend for the desktop UI (instagrapi, session-based).

ig_session.json holds the account session in plaintext next to this file;
treat it like a password and never commit, share, or transmit it.
"""
import threading
import re
import subprocess
import tempfile
from pathlib import Path

SESSION_FILE = Path(__file__).parent / 'ig_session.json'


class VoiceSender:
    """Session-based voice-note sender. UI thread stays responsive via worker."""

    def __init__(self, on_status):
        self.on_status = on_status          # callable(str) from any thread
        self._client = None
        self._lock = threading.Lock()
        self._username = None
        self._user_id = None
        self._busy = False
        self._status = 'Not connected'
        self._message_id = None
        self._state_lock = threading.Lock()

    def _report(self, text):
        self._status = text
        self.on_status(text)

    def state(self):
        return dict(connected=self.logged_in, username=self._username,
                    busy=self._busy, status=self._status, message_id=self._message_id)

    def disconnect(self):
        with self._state_lock:
            if self._busy:
                raise ValueError('Operation in progress.')
            self._client = None
            self._username = None
            self._report('Disconnected. Saved session kept.')
        return True

    # ---- session ------------------------------------------------------------
    @property
    def logged_in(self):
        return self._client is not None

    def session_username(self):
        return self._username

    def connect(self):
        """Load and validate the saved session in a worker thread."""
        with self._state_lock:
            if self._busy:
                raise ValueError('Operation in progress.')
            if self._client is not None:
                return True
            self._busy = True
        threading.Thread(target=self._connect, daemon=True).start()
        return True

    def _connect(self):
        try:
            from safe_client import SafeClient as Client
            if not SESSION_FILE.exists():
                self._report('No session found. Run "Import Session.cmd" first.')
                return
            cl = Client()
            cl.delay_range = [1, 2]
            cl.load_settings(str(SESSION_FILE))
            self._report('Checking session…')
            info = cl.account_info()
            self._client = cl
            self._username = info.username
            self._user_id = cl.user_id
            self._report(f'Connected as @{info.username}')
        except Exception as exc:
            self._client = None
            self._report(f'Session invalid ({type(exc).__name__}). Re-import via Import Session.cmd')
        finally:
            self._busy = False

    # ---- sending ------------------------------------------------------------
    def send_voice(self, target_username, audio_path, confirmed=False):
        if confirmed is not True:
            raise ValueError('Confirm the recipient and audio file before sending.')
        with self._state_lock:
            if self._busy:
                raise ValueError('Operation in progress; no message queued.')
            if not self.logged_in:
                raise ValueError('Connect your saved session first.')
            target = str(target_username).strip().lstrip('@')
            if not re.fullmatch(r'[A-Za-z0-9_.]{1,30}', target):
                raise ValueError('Enter an Instagram username, not a URL.')
            if not audio_path or not Path(audio_path).is_file():
                raise ValueError('Open an audio file first.')
            self._busy = True
            self._message_id = None
            self._report('Preparing voice note…')
        def work():
            try:
                self._send(target, audio_path)
            finally:
                self._busy = False
        threading.Thread(target=work, daemon=True).start()
        return True

    def _prepare_audio(self, path, directory):
        output = Path(directory) / 'voice.m4a'
        result = subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin',
            '-y','-i',str(path),'-vn','-ac','1','-ar','44100','-c:a','aac',
            '-b:a','96k',str(output)], capture_output=True, timeout=120,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode or not output.is_file() or output.stat().st_size < 100:
            raise ValueError('Audio conversion failed.')
        return output

    def _send(self, target_username, audio_path):
        with self._lock:
            cl = self._client
            if cl is None:
                self._report('Not connected. Session missing or invalid.')
                return
            if not target_username or not target_username.strip():
                self._report('Enter the recipient username first.')
                return
            path = Path(audio_path)
            if not path.exists():
                self._report('Audio file not found. Open a file first.')
                return
            target = target_username.strip().lstrip('@')
            if target.lower() == (self._username or '').lower():
                self._report(f'Sending to yourself (@{target})…')
            else:
                self._report(f'Resolving @{target}…')
            try:
                user_id = cl.user_id_from_username(target)
                self._report(f'Uploading voice note to @{target}…')
                with tempfile.TemporaryDirectory(prefix='instavoice-') as directory:
                    prepared = self._prepare_audio(path, directory)
                    message = cl.direct_send_voice(prepared, [user_id])
                message_id = getattr(message, 'id', None)
                if not isinstance(message_id, (str, int)) or not str(message_id):
                    self._report('No message receipt returned. Delivery unknown; check Instagram before retrying.')
                    return
                self._message_id = str(message_id)
                self._report(f'✓ Voice note sent to @{target} (API accepted; receipt {message_id})')
            except Exception as exc:
                msg = str(exc)
                if 'user_not_found' in msg.lower():
                    self._report(f'✗ No Instagram account named "{target}"')
                else:
                    self._report(f'Send failed ({type(exc).__name__}). Check Instagram before retrying; no automatic retry.')
