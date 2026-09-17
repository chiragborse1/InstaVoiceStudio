"""Exercise the actual library session fallback without network."""
import contextlib
import io
import logging
import unittest
from unittest.mock import patch
from instagrapi.exceptions import PrivateError, ClientError
import ig_session_import

class FallbackPrivacyTests(unittest.TestCase):
    def test_real_session_fallback_does_not_log_sensitive_response(self):
        secret = 'SYNTHETIC-PRIVATE-RESPONSE-DO-NOT-LOG'
        output, logs = io.StringIO(), io.StringIO()
        root = logging.getLogger()
        handler = logging.StreamHandler(logs)
        root.addHandler(handler)
        try:
            with patch('ig_session_import.getpass.getpass',return_value='12345%3A'+'a'*40), \
                 patch('safe_client.SafeClient.user_info_v1',side_effect=PrivateError('fallback')), \
                 patch('safe_client.SafeClient.private_request',side_effect=ClientError(secret)), \
                 patch('safe_client.SafeClient.user_short_gql',side_effect=ClientError(secret)), \
                 contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self.assertEqual(ig_session_import.main(),2)
            self.assertNotIn(secret,logs.getvalue()+output.getvalue())
            logging.getLogger('unrelated.application').warning('unrelated-visible')
            self.assertIn('unrelated-visible',logs.getvalue())
        finally:
            root.removeHandler(handler)

if __name__=='__main__': unittest.main()
