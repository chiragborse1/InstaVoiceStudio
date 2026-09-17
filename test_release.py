"""Offline portability regressions. All audio fixtures are generated locally."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf


class ReleaseTests(unittest.TestCase):
    def test_microphone_cap_reports_limit_and_keeps_final_frames(self):
        from desktop import Api
        api = Api()
        api.inputs = {'Microphone': 0}
        with patch('desktop.sd.InputStream') as stream:
            api.start_recording('Microphone')
            api._record_frames = 48000 * 600 - 2
            callback = stream.call_args.kwargs['callback']
            callback(np.ones((4, 1), dtype=np.float32), 4, None, None)
            self.assertEqual(api._record_frames, 48000 * 600)
            self.assertEqual(len(api._record_chunks[-1]), 2)
            status = api.status()
            self.assertTrue(status['recordingLimitReached'])
            self.assertEqual(status['recordingSeconds'], 600)
            self.assertTrue(any('limit' in line and 'Stop' in line for line in status['logs']))
            callback(np.ones((4, 1), dtype=np.float32), 4, None, None)
            self.assertEqual(len(api._record_chunks), 1)
        api.close()

    def test_device_selection_respects_system_default(self):
        from desktop import Api
        api = Api()
        devices = [
            dict(name='System speakers', hostapi=0, max_output_channels=2, max_input_channels=0),
            dict(name='Bluetooth Headphones', hostapi=0, max_output_channels=2, max_input_channels=0),
        ]
        apis = [dict(name='Windows WASAPI', default_output_device=0, default_input_device=-1)]
        with patch('desktop.sd._terminate'), patch('desktop.sd._initialize'), \
             patch('desktop.sd.query_devices', return_value=devices), \
             patch('desktop.sd.query_hostapis', return_value=apis):
            self.assertEqual(api.devices()['default'], 'System speakers')
        api.close()

    def test_audio_engine_is_standalone(self):
        self.assertIsNotNone(importlib.util.find_spec('audio_engine'),
                             'Audio engine must not depend on the legacy browser GUI')
        from audio_engine import AudioEngine
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'generated.wav'
            sf.write(path, np.ones((480, 2), dtype=np.float32) * .25, 48000)
            data, rate = AudioEngine.load_audio(path, lead_in=0, tail=0)
        self.assertEqual(rate, 48000)
        self.assertEqual(data.shape, (480,))
        np.testing.assert_allclose(data, .25)
        result = subprocess.run([sys.executable, '-c',
            "import desktop, sys; a=desktop.Api(); a.close(); "
            "assert not {'studio','connector','playwright','tkinter'} & set(sys.modules)"],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
