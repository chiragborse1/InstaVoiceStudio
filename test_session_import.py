"""Importer privacy tests: fake client only, never a real login."""
import contextlib
import io
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import ig_session_import as importer


class ImportTests(unittest.TestCase):
    def test_failure_never_prints_or_logs_token(self):
        token = 'offline-sensitive-fixture'
        client = importer.Client()
        self.addCleanup(client.private.close)
        self.addCleanup(client.public.close)
        def fail(_):
            client.logger.error('request contained %s', token)
            client.private_request_logger.error('request contained %s', token)
            client.public_request_logger.error('request contained %s', token)
            raise RuntimeError(token)
        client.login_by_sessionid = Mock(side_effect=fail)
        client.dump_settings = Mock()
        output, logs = io.StringIO(), io.StringIO()
        handler = logging.StreamHandler(logs)
        logger = logging.getLogger('instagrapi')
        logger.addHandler(handler)
        try:
            with patch.object(importer, 'Client', return_value=client), \
                 patch.object(importer.getpass, 'getpass', return_value=token), \
                 contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self.assertEqual(importer.main(), 2)
        finally:
            logger.removeHandler(handler)
        self.assertNotIn(token, output.getvalue() + logs.getvalue())
        self.assertIn('plaintext', output.getvalue().lower())
        client.dump_settings.assert_not_called()

    def test_import_does_not_disable_other_application_logging(self):
        client = importer.Client()
        self.addCleanup(client.private.close)
        self.addCleanup(client.public.close)
        previous_disable = logging.root.manager.disable
        def fail(_):
            self.assertEqual(logging.root.manager.disable, previous_disable)
            logging.getLogger('offline-other-app').warning('other-app-visible')
            raise RuntimeError('offline failure')
        client.login_by_sessionid = Mock(side_effect=fail)
        with self.assertLogs('offline-other-app', level='WARNING') as captured, \
             patch.object(importer, 'Client', return_value=client), \
             patch.object(importer.getpass, 'getpass', return_value='offline-token'), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(importer.main(), 2)
        self.assertIn('other-app-visible', ''.join(captured.output))

    def test_blank_hidden_input_aborts_without_client(self):
        with patch.object(importer, 'Client') as client, \
             patch.object(importer.getpass, 'getpass', return_value='  '), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(importer.main(), 1)
        client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
