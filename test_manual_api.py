import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
import soundfile as sf
from desktop import Api

class ManualApiTests(unittest.TestCase):
    def test_loaded_file_is_used_for_confirmed_send_only(self):
        api=Api()
        api._sender=Mock()
        api._sender.state.return_value={'busy':False}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'clip.wav'; sf.write(p,np.zeros(4800),48000)
            api.load_file(str(p))
            with self.assertRaisesRegex(ValueError,'Confirm'):
                api.send_voice('example_user',False)
            api._sender.send_voice.assert_not_called()
            api.send_voice('example_user',True)
            api._sender.send_voice.assert_called_once_with('example_user',str(p.resolve()),confirmed=True)
        api.close()

    def test_mic_record_stop_produces_selected_clip(self):
        api=Api()
        api.inputs={'Test microphone':1}
        with tempfile.TemporaryDirectory() as d, patch('desktop.RECORDINGS',Path(d)), patch('desktop.sd.InputStream') as stream:
            api.start_recording('Test microphone')
            callback=stream.call_args.kwargs['callback']
            callback(np.ones((4800,1),dtype=np.float32)*.1,4800,None,None)
            self.assertTrue(api.status()['recording'])
            clip=api.stop_recording()
            self.assertAlmostEqual(clip['duration'],.1,places=2)
            self.assertFalse(api.status()['recording'])
            self.assertTrue(Path(api._audio_path).is_file())
        api.close()

    def test_preview_volume_and_speed(self):
        api=Api();api.outputs={'Test':1};api.buf=np.ones(4800,dtype=np.float32);api.sr=48000
        api.engine.play=Mock()
        api.play('Test',False,'',.25,2)
        args=api.engine.play.call_args.args
        self.assertEqual(len(args[0]),2400)
        self.assertAlmostEqual(float(args[0].max()),.25)
        api.close()

if __name__=='__main__': unittest.main()
