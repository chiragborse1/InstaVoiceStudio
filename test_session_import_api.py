"""Offline tests for in-app session import."""
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from desktop import Api

class SessionImportTests(unittest.TestCase):
    def test_import_session_valid_token(self):
        api=Api()
        api._sender=Mock()
        with patch('safe_client.SafeClient') as MockClient:
            cl=MockClient.return_value
            cl.login_by_sessionid.return_value=True
            cl.username='new_user'
            username=api.import_session('valid-session-token')
            self.assertEqual(username,'new_user')
            cl.dump_settings.assert_called_once()
        api.close()

    def test_import_session_empty_token_raises(self):
        api=Api()
        with self.assertRaisesRegex(ValueError,'Empty session token'):
            api.import_session('')
        with self.assertRaisesRegex(ValueError,'Empty session token'):
            api.import_session('   ')
        api.close()

    def test_import_session_invalid_token_raises(self):
        api=Api()
        with patch('safe_client.SafeClient') as MockClient:
            cl=MockClient.return_value
            cl.login_by_sessionid.return_value=False
            with self.assertRaisesRegex(ValueError,'import failed'):
                api.import_session('bad-token')
        api.close()

    def test_import_session_exception_raises(self):
        api=Api()
        with patch('safe_client.SafeClient') as MockClient:
            MockClient.side_effect=Exception('disk full')
            with self.assertRaisesRegex(ValueError,'failed'):
                api.import_session('any-token')
        api.close()

if __name__=='__main__': unittest.main()