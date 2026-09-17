"""Local audio loading and playback; no browser, profile, or network dependency."""
import queue
import numpy as np
import sounddevice as sd
import soundfile as sf

VIRTUAL_HINTS = ("virtual", "cable", "hitpaw", "voice changer", "vb-audio", "voicemeeter")


class AudioEngine:
    """Device discovery, playback with routing/speed, and input level meter."""

    def __init__(self):
        self.play_stream = None
        self.monitor_stream = None
        self.meter_stream = None
        self._buf = None
        self._pos = 0
        self._playing = False
        self.on_progress = None      # callback(fraction 0..1)
        self.on_finished = None      # callback()
        self.meter_queue = queue.Queue(maxsize=10)

    # -- devices -----------------------------------------------------------
    @staticmethod
    def list_devices():
        """Return {'outputs': [...], 'inputs': [...]} with device indices."""
        outs, ins = [], []
        for i, d in enumerate(sd.query_devices()):
            entry = {"index": i, "name": d["name"], "channels": d["max_output_channels"] or d["max_input_channels"],
                     "virtual": any(h in d["name"].lower() for h in VIRTUAL_HINTS)}
            if d["max_output_channels"] > 0:
                outs.append(entry)
            if d["max_input_channels"] > 0:
                ins.append(entry)
        return {"outputs": outs, "inputs": ins}

    # -- file prep ----------------------------------------------------------
    @staticmethod
    def load_audio(path, speed=1.0, lead_in=0.3, tail=0.15, target_sr=None):
        """Load file, prepend silence, apply speed. Returns (float32 mono array, sr)."""
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        mono = data.mean(axis=1)
        if speed != 1.0 and speed > 0:
            n_out = int(round(len(mono) / speed))
            x_new = np.linspace(0.0, len(mono) - 1, num=n_out)
            mono = np.interp(x_new, np.arange(len(mono)), mono).astype(np.float32)
        if target_sr and sr != target_sr:
            n_out = int(len(mono) * target_sr / sr)
            mono = np.interp(np.linspace(0, len(mono) - 1, n_out), np.arange(len(mono)), mono).astype(np.float32)
            sr = target_sr
        lead = np.zeros(int(sr * lead_in), dtype=np.float32)
        t = np.zeros(int(sr * tail), dtype=np.float32)
        buf = np.concatenate([lead, mono, t])
        return buf, sr

    @staticmethod
    def file_duration(path):
        try:
            info = sf.info(path)
            return info.frames / info.samplerate
        except Exception:
            return 0.0

    # -- playback -----------------------------------------------------------
    def play(self, buf, sr, out_device=None, monitor_device=None, speed=1.0):
        """Independent cursors and buffers for each output; no global sd.play."""
        self.stop()
        source = np.asarray(buf, dtype=np.float32)
        if not len(source):
            raise ValueError('Audio file is empty')
        devices = list(dict.fromkeys(d for d in (out_device, monitor_device) if d is not None)) or [None]
        self.streams = []
        self._playing = True
        done = set()
        progress_cb, finish_cb = self.on_progress, self.on_finished

        def callback_for(data, number):
            pos = 0
            def callback(outdata, frames, timing, status):
                nonlocal pos
                outdata.fill(0)
                if not self._playing:
                    raise sd.CallbackStop
                end = min(pos + frames, len(data))
                chunk = data[pos:end]
                outdata[:len(chunk), :] = chunk[:, None]
                pos = end
                if number == 0 and progress_cb:
                    progress_cb(pos / len(data))
                if pos >= len(data):
                    done.add(number)
                    if len(done) == len(devices):
                        self._playing = False
                        if finish_cb:
                            finish_cb()
                    raise sd.CallbackStop
            return callback

        try:
            for number, device in enumerate(devices):
                info = sd.query_devices(device, 'output')
                channels = min(2, int(info['max_output_channels']))
                rate = sr
                try:
                    sd.check_output_settings(device=device, channels=channels, samplerate=rate)
                except sd.PortAudioError:
                    rate = int(info['default_samplerate'])
                    sd.check_output_settings(device=device, channels=channels, samplerate=rate)
                data = source
                if rate != sr:
                    data = np.interp(np.linspace(0, len(source)-1, round(len(source)*rate/sr)),
                                     np.arange(len(source)), source).astype(np.float32)
                stream = sd.OutputStream(device=device, samplerate=rate, channels=channels,
                                         callback=callback_for(data, number))
                self.streams.append(stream)
            for stream in self.streams:
                stream.start()
        except Exception as exc:
            self.stop()
            raise RuntimeError(f'Could not open selected output. Refresh devices and select again: {exc}') from exc

    def stop(self):
        self._playing = False
        for stream in getattr(self, 'streams', []):
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self.streams = []

    @property
    def playing(self):
        return self._playing
