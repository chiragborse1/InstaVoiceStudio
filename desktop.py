"""WebView2 desktop shell. Local Tabler UI and standalone audio engine.
Manual recording and confirmed voice-note sending controls.
"""
from pathlib import Path
import json
import threading
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import subprocess
import tempfile
import uuid
from voice_sender import VoiceSender
from audio_engine import AudioEngine

BASE = Path(__file__).resolve().parent
RECORDINGS = BASE / 'recordings'


class Api:
    def __init__(self):
        self._window = None
        self.engine = AudioEngine()
        self.lock = threading.RLock()
        self.outputs = {}
        self.buf = None
        self.sr = 48000
        self.progress = 0.0
        self.logs = []
        self.engine.on_progress = self._progress
        self.engine.on_finished = self._finished
        self.finished = False
        self._sender = VoiceSender(self._log)
        self._audio_path = None
        self._file = None
        self.inputs = {}
        self._record_stream = None
        self._record_chunks = []
        self._mic_level = 0.0
        self._record_frames = 0
        self._record_limit_reached = False

    def _log(self, text):
        self.logs.append(str(text))
        self.logs = self.logs[-30:]

    def _progress(self, value):
        self.progress = value

    def _finished(self):
        self.finished = True

    def devices(self):
        with self.lock:
            if self._record_stream is not None:
                raise ValueError('Stop recording before refreshing devices.')
            self.engine.stop()
            sd._terminate()
            sd._initialize()
            devices, apis = sd.query_devices(), sd.query_hostapis()
            selected = next((i for i,a in enumerate(apis) if a['name']=='Windows WASAPI'), 0)
            self.outputs = {d['name']:i for i,d in enumerate(devices)
                            if d['hostapi']==selected and d['max_output_channels']>0}
            default = apis[selected]['default_output_device']
            preferred = next((name for name,index in self.outputs.items() if index==default),'')
            names = list(self.outputs)
            virtual = [name for name in names if any(h in name.lower() for h in ('virtual','cable','voicemeeter'))]
            self.inputs = {d['name']:i for i,d in enumerate(devices)
                           if d['hostapi']==selected and d['max_input_channels']>0}
            input_default = next((n for n,i in self.inputs.items()
                                  if i==apis[selected]['default_input_device']), '')
            return {'outputs':names, 'virtual':virtual, 'default':preferred,
                    'inputs':list(self.inputs), 'inputDefault':input_default}

    def choose_file(self):
        import webview
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False,
                    file_types=('Audio (*.wav;*.mp3;*.flac;*.ogg;*.m4a;*.aac)',))
        return self.load_file(paths[0]) if paths else None

    def load_file(self, path):
        with self.lock:
            self.engine.stop()
            if self._record_stream is not None:
                raise ValueError('Stop microphone recording first.')
            if self._sender.state()['busy']:
                raise ValueError('Wait for the current Instagram operation.')
            try:
                buf,sr = self.engine.load_audio(path,lead_in=0,tail=0)
            except Exception:
                with tempfile.TemporaryDirectory(prefix='instavoice-decode-') as directory:
                    wav = Path(directory)/'decoded.wav'
                    result = subprocess.run(['ffmpeg','-hide_banner','-loglevel','error',
                        '-nostdin','-y','-i',str(path),'-vn','-ac','1','-ar','48000',str(wav)],
                        capture_output=True,timeout=120,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    if result.returncode:
                        raise ValueError('Cannot decode this audio file.')
                    buf,sr = self.engine.load_audio(wav,lead_in=0,tail=0)
            if len(buf)==0:
                raise ValueError('The recording is empty.')
            if not np.isfinite(buf).all():
                raise ValueError('The file contains invalid audio samples.')
            self.buf,self.sr = buf,sr
            self.progress = 0
            peaks = [float(np.max(np.abs(chunk))) if len(chunk) else 0
                     for chunk in np.array_split(buf,96)]
            self._audio_path = str(Path(path).resolve())
            self._file = {'name':Path(path).name, 'duration':len(buf)/sr,
                          'peaks':peaks, 'sampleRate':sr}
            return self._file

    def _device(self, name):
        if name not in self.outputs:
            raise ValueError('Select a connected output. Refresh devices if your headphones disconnected.')
        return self.outputs[name]

    def play(self, speaker, route_enabled=False, route='', volume=1.0, speed=1.0):
        with self.lock:
            if self.buf is None:
                raise ValueError('Open an audio file first.')
            output = self._device(speaker)
            virtual = self._device(route) if route_enabled else None
            self.progress = 0
            self.finished = False
            if self._record_stream is not None:
                raise ValueError('Stop microphone recording before playback.')
            volume, speed = float(volume), float(speed)
            if not 0 <= volume <= 1 or not .5 <= speed <= 2:
                raise ValueError('Invalid preview volume or speed.')
            audio = self.buf
            if speed != 1:
                count = max(1, round(len(audio)/speed))
                audio = np.interp(np.linspace(0,len(audio)-1,count),np.arange(len(audio)),audio)
            self.engine.play((audio*volume).astype(np.float32),self.sr,out_device=output,monitor_device=virtual)
            return {'speaker':speaker,'route':route if route_enabled else None}

    def stop(self):
        with self.lock:
            self.engine.stop()
            return True

    def test_sound(self, speaker):
        with self.lock:
            output = self._device(speaker)
            t = np.arange(31200)/48000
            tone = (.045*np.sin(2*np.pi*523.25*t)*np.sin(np.pi*t/.65)**2).astype(np.float32)
            self.progress = 0
            self.finished = False
            self.engine.play(tone,48000,out_device=output,monitor_device=None)
            return True

    def status(self):
        return {'progress':self.progress,'playing':self.engine.playing,
                'browser':False, 'logs':self.logs[-8:],
                'voice':self._sender.state(), 'file':self._file,
                'recording':self._record_stream is not None, 'micLevel':self._mic_level,
                'recordingLimitReached':self._record_limit_reached,
                'recordingSeconds':self._record_frames / 48000}

    def open_instagram(self):
        import webbrowser
        webbrowser.open('https://www.instagram.com/direct/inbox/')
        return True

    def connect_voice(self):
        return self._sender.connect()

    def disconnect_voice(self):
        return self._sender.disconnect()

    def import_session(self, token):
        """Validate and save a sessionid token from the in-app panel.
        Returns the username on success, raises ValueError on failure.
        The token is never logged or printed."""
        from safe_client import SafeClient as Client
        SESSION_FILE = BASE / 'ig_session.json'
        if not token or not token.strip():
            raise ValueError('Empty session token.')
        try:
            cl = Client()
            cl.delay_range = [2, 6]
            if not cl.login_by_sessionid(token.strip()):
                raise ValueError('Session not accepted by Instagram.')
            cl.dump_settings(str(SESSION_FILE))
            username = getattr(cl, 'username', None) or 'unknown'
            self._log(f'Session imported for @{username}')
            return username
        except Exception as exc:
            self._log(f'Session import failed: {type(exc).__name__}')
            raise ValueError('Session import failed. Check the token and folder permissions.')

    def send_voice(self, username, confirmed=False):
        with self.lock:
            if confirmed is not True:
                raise ValueError('Confirm the recipient and file first.')
            if self._record_stream is not None:
                raise ValueError('Stop microphone recording before sending.')
            if not self._audio_path:
                raise ValueError('Open an audio file first.')
            return self._sender.send_voice(username,self._audio_path,confirmed=True)

    def start_recording(self, mic):
        with self.lock:
            if self._record_stream is not None:
                raise ValueError('Already recording.')
            if mic not in self.inputs:
                raise ValueError('Select a connected microphone.')
            if self._sender.state()['busy']:
                raise ValueError('Wait for the current Instagram operation.')
            self.engine.stop()
            self._record_chunks = []
            self._record_frames = 0
            self._record_limit_reached = False
            self._mic_level = 0
            self._log('Recording started. Maximum 10 minutes; Stop recording saves the clip.')
            def capture(data, frames, timing, status):
                remaining = max(0, 48000 * 600 - self._record_frames)
                count = min(remaining, frames, len(data))
                if count:
                    chunk = data[:count].copy()
                    self._record_chunks.append(chunk)
                    self._record_frames += count
                    self._mic_level = float(np.max(np.abs(chunk)))
                if self._record_frames >= 48000 * 600 and not self._record_limit_reached:
                    self._record_limit_reached = True
                    self._mic_level = 0
                    self._log('10-minute recording limit reached. Capture paused; click Stop recording to save.')
            stream = sd.InputStream(device=self.inputs[mic],channels=1,samplerate=48000,
                                    dtype='float32',callback=capture)
            try:
                stream.start()
            except Exception:
                stream.close()
                raise
            self._record_stream = stream
            return True

    def stop_recording(self):
        with self.lock:
            if self._record_stream is None:
                raise ValueError('Microphone is not recording.')
            stream, self._record_stream = self._record_stream, None
            stream.stop()
            stream.close()
            self._mic_level = 0
            if not self._record_chunks:
                raise ValueError('No microphone audio captured.')
            audio = np.concatenate(self._record_chunks).reshape(-1)
            self._record_chunks = []
            RECORDINGS.mkdir(exist_ok=True)
            path = RECORDINGS / ('recording-'+uuid.uuid4().hex[:12]+'.wav')
            sf.write(path,audio,48000)
            return self.load_file(str(path))

    def close(self):
        if self._record_stream is not None:
            self._record_stream.stop()
            self._record_stream.close()
            self._record_stream = None
        self.engine.stop()


def main():
    import sys
    import webview
    api = Api()
    window = webview.create_window('InstaVoice Studio',str(BASE/'ui'/'index.html'),js_api=api,
                   width=1100,height=790,min_size=(920,680),background_color='#f7f8fa')
    api._window = window
    window.events.closed += api.close
    if '--smoke' in sys.argv:
        def smoke():
            try:
                for _ in range(80):
                    ready = window.evaluate_js('Boolean(window.appReady)')
                    if ready: break
                    time.sleep(.1)
                assert ready, 'Desktop JS bridge did not initialize'
                window.evaluate_js('''(async () => {
                    try {
                        const link = document.querySelector('link[rel="stylesheet"]');
                        const response = await fetch(link.href);
                        const css = await response.text();
                        const body = getComputedStyle(document.body);
                        const heading = getComputedStyle(document.querySelector('h1'));
                        window.visualCheck = {
                            cssURL: link.href, cssStatus: response.status,
                            cssBytes: css.length, tablerLoaded: css.includes('--tblr-'),
                            bodyFont: body.fontFamily, headingFont: heading.fontFamily,
                            background: body.backgroundColor,
                            boxSizing: body.boxSizing,
                            scrollWidth: document.documentElement.scrollWidth,
                            clientWidth: document.documentElement.clientWidth,
                            speaker: document.querySelector('#speaker').value,
                            ready: window.appReady
                        };
                    } catch (e) { window.visualCheck = {error:String(e)}; }
                })()''')
                result = None
                for _ in range(100):
                    result = window.evaluate_js('window.visualCheck || null')
                    if result: break
                    time.sleep(.05)
                assert result, 'No DOM verification result'
                checks = {
                    'stylesheet_served': result.get('cssStatus') == 200,
                    'tabler_loaded': result.get('tablerLoaded') and result.get('cssBytes',0) > 100000,
                    'sans_serif_font': 'sans-serif' in result.get('bodyFont',''),
                    'light_background': result.get('background') == 'rgb(247, 248, 250)',
                    'box_sizing': result.get('boxSizing') == 'border-box',
                    'no_horizontal_overflow': result.get('scrollWidth',1) <= result.get('clientWidth',0),
                    'device_selected': bool(result.get('speaker')),
                    'bridge_ready': result.get('ready') is True,
                }
                result['checks'] = checks
                (BASE/'webview-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                print('WEBVIEW VERIFICATION:',json.dumps(result),flush=True)
                assert all(checks.values()), f'Failed visual checks: {checks}'
            except Exception:
                import traceback
                traceback.print_exc()
                import os
                os._exit(1)
            finally:
                window.destroy()
        webview.start(smoke,gui='edgechromium',icon=str(BASE/'ui'/'assets'/'app.ico'))
    else:
        webview.start(gui='edgechromium',icon=str(BASE/'ui'/'assets'/'app.ico'))

if __name__=='__main__': main()