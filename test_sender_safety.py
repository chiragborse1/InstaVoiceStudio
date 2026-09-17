"""Offline safety tests: never use a real session or network."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from voice_sender import VoiceSender

class SenderSafetyTests(unittest.TestCase):
    def test_requires_explicit_confirmation(self):
        sender = VoiceSender(lambda _: None)
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            sender.send_voice('example_user', 'missing.wav', confirmed=False)

    def test_busy_rejects_instead_of_queuing(self):
        sender = VoiceSender(lambda _: None)
        sender._busy = True
        with self.assertRaisesRegex(ValueError, 'progress'):
            sender.send_voice('example_user', 'missing.wav', confirmed=True)

    def test_success_records_returned_message_id(self):
        messages=[]
        sender = VoiceSender(messages.append)
        sender._client=Mock()
        sender._client.direct_send_voice.return_value=Mock(id='offline-message-123')
        sender._client.user_id_from_username.return_value='123'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'audio.m4a'; p.write_bytes(b'offline fixture')
            with patch.object(sender, '_prepare_audio', return_value=p):
                sender._send('example_user', str(p))
        self.assertEqual(getattr(sender, '_message_id', None), 'offline-message-123')
        self.assertTrue(any('Voice note sent' in x for x in messages))

    def test_missing_receipt_is_not_success(self):
        messages=[]
        sender = VoiceSender(messages.append)
        sender._client=Mock()
        sender._client.direct_send_voice.return_value=None
        sender._client.user_id_from_username.return_value='123'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'audio.m4a'; p.write_bytes(b'offline fixture')
            with patch.object(sender, '_prepare_audio', return_value=p):
                sender._send('example_user', str(p))
        self.assertFalse(any('Voice note sent' in x for x in messages))
        self.assertTrue(any('receipt' in x.lower() for x in messages))

if __name__=='__main__': unittest.main()
