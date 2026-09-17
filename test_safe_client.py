"""Offline tests of the real instagrapi broadcast path; no saved credentials."""
import contextlib
import io
import json
import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from instagrapi import Client
from instagrapi.exceptions import ClientIncompleteReadError, ClientRequestTimeout
from voice_sender import VoiceSender


class SafeClientTests(unittest.TestCase):
    def setUp(self):
        # Default-deny every requests session, including fresh upload sessions.
        def blocked(*args, **kwargs):
            raise AssertionError('Unexpected network in offline test')
        self.network = patch.object(requests.Session, 'send', new=blocked)
        self.network.start()
        self.addCleanup(self.network.stop)

    def connected_sender(self):
        sender = VoiceSender(lambda _: None)
        # Only synthetic session metadata; never read ig_session.json.
        with patch('voice_sender.SESSION_FILE') as session, \
             patch.object(Client, 'load_settings'), \
             patch.object(Client, 'account_info', return_value=SimpleNamespace(username='offline_owner')):
            session.exists.return_value = True
            sender._connect()
        self.assertTrue(sender.logged_in, sender.state())
        client = sender._client
        self.addCleanup(client.private.close)
        self.addCleanup(client.public.close)
        client.authorization_data = {'ds_user_id': '123', 'sessionid': 'offline-session'}
        client.delay_range = None
        return sender

    def test_transport_and_public_requests_have_no_retries(self):
        sender = self.connected_sender()
        client = sender._client
        self.assertEqual(client.session_retry_total, 0)
        # Upstream calls this retries_count, but range(count) counts attempts.
        self.assertEqual(client.public_request_retries_count, 1)
        for session in (client.private, client.public):
            for adapter in session.adapters.values():
                self.assertEqual(adapter.max_retries.total, 0)
        with patch.object(client, '_send_public_request', side_effect=ClientRequestTimeout()) as send:
            with self.assertRaises(ClientRequestTimeout):
                client.public_request('https://offline.invalid')
            self.assertEqual(send.call_count, 1)

    def test_saved_settings_cannot_restore_transport_retries(self):
        client = self.connected_sender()._client
        # Exercise the real load_settings path using only generated settings.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.json'
            path.write_text(json.dumps({'session_retry_total': 3,
                                        'public_request_retries_count': 3,
                                        'private_transport': 'requests'}))
            client.load_settings(path)
        self.assertEqual(client.session_retry_total, 0)
        self.assertEqual(client.public_request_retries_count, 1)
        for session in (client.private, client.public):
            for adapter in session.adapters.values():
                self.assertEqual(adapter.max_retries.total, 0)

    def test_private_preprocessing_and_challenge_never_replay(self):
        from instagrapi.exceptions import ChallengeRequired
        client = self.connected_sender()._client
        client.delay_range = [1, 2]
        headers = {'X-Offline': 'fixture'}
        before = client.private_requests_count
        with patch('safe_client.random_delay') as delay, \
             patch.object(client, '_send_private_request', return_value={'status': 'ok'}) as send:
            result = client.private_request('offline/', data={'a': 'b'}, params={'q': 'v'},
                                            headers=headers, extra_sig=['extra'], domain='offline.invalid')
        delay.assert_called_once_with(delay_range=[1, 2])
        self.assertEqual(client.private_requests_count, before + 1)
        self.assertEqual(result, {'status': 'ok'})
        self.assertEqual(headers, {'X-Offline': 'fixture'})
        self.assertEqual(send.call_args.kwargs, dict(
            data={'a': 'b'}, params={'q': 'v'}, login=False, with_signature=True,
            headers={'X-Offline': 'fixture', 'Authorization': client.authorization},
            extra_sig=['extra'], domain='offline.invalid'))
        with patch('safe_client.random_delay'), \
             patch.object(client, '_send_private_request', side_effect=ChallengeRequired()) as send, \
             patch.object(client, 'challenge_resolve') as challenge:
            with self.assertRaises(ChallengeRequired):
                client.private_request('offline/')
            send.assert_called_once()
            challenge.assert_not_called()

    def test_fresh_voice_upload_transport_has_no_retries(self):
        client = self.connected_sender()._client
        for error in (requests.exceptions.ChunkedEncodingError, requests.exceptions.Timeout):
            with self.subTest(error=error.__name__):
                attempts = []
                def boundary(session, request, **kwargs):
                    for adapter in session.adapters.values():
                        self.assertEqual(adapter.max_retries.total, 0)
                    attempts.append(request.method)
                    if request.method == 'POST':
                        raise error('offline upload failure')
                    response = requests.Response()
                    response.status_code = 200
                    response._content = b'{"offset":0}'
                    return response
                with patch.object(requests.Session, 'send', autospec=True, side_effect=boundary):
                    with self.assertRaises(error):
                        client._voice_rupload(b'offline audio', '123', 456)
                self.assertEqual(attempts, ['GET', 'POST'])

    def test_account_lookup_and_send_do_not_log_secrets(self):
        secret = 'SYNTHETIC-SECRET-NOT-A-REAL-COOKIE'
        sender = self.connected_sender()
        client = sender._client
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        loggers = [logging.getLogger(name) for name in
                   ('', 'instagrapi', 'private_request', 'public_request')]
        old_levels = [logger.level for logger in loggers]
        previous_disable = logging.root.manager.disable
        for logger in loggers:
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)

        def response_boundary(session, request, **kwargs):
            response = requests.Response()
            response.request = request
            response.url = request.url + '?synthetic=' + secret
            response.status_code = 200
            # Upstream logs this body before parsing/extracting account/message.
            response._content = json.dumps({'status': 'ok', 'secret': secret}).encode()
            response.raw = io.BytesIO(response.content)
            return response

        try:
            with patch.object(requests.Session, 'send', autospec=True, side_effect=response_boundary), \
                 patch('instagrapi.mixins.private.time.sleep'), \
                 contextlib.redirect_stderr(output), contextlib.redirect_stdout(output):
                with self.assertRaises(KeyError):
                    client.account_info()
                # Actual public request logger plus username fallback exception logging.
                client.public_request('https://offline.invalid', return_json=True)
                with patch.object(client, 'user_info_by_username_v1', side_effect=RuntimeError(secret)), \
                     patch.object(client, '_user_info_by_username_public', side_effect=RuntimeError(secret)):
                    with self.assertRaises(RuntimeError):
                        client.user_id_from_username('offline_unique_target')
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / 'offline.m4a'
                    path.write_bytes(b'offline fixture')
                    with patch.object(client, 'user_id_from_username', return_value='456'), \
                         patch.object(client, '_direct_thread_id_from_user_ids', return_value=789), \
                         patch.object(client, '_voice_rupload', return_value=101), \
                         patch.object(sender, '_prepare_audio', return_value=path):
                        sender._send('offline_target', path)
                # Unrelated application logging must remain live (no global toggle).
                logging.getLogger('offline-other-app').warning('other-app-visible')
            self.assertNotIn(secret, output.getvalue() + sender.state()['status'])
            self.assertIn('other-app-visible', output.getvalue())
            self.assertEqual(logging.root.manager.disable, previous_disable)
        finally:
            for logger, level in zip(loggers, old_levels):
                logger.removeHandler(handler)
                logger.setLevel(level)

    def test_broadcast_is_attempted_once_on_incomplete_read_and_timeout(self):
        for error in (ClientIncompleteReadError, ClientRequestTimeout):
            with self.subTest(error=error.__name__):
                sender = self.connected_sender()
                client = sender._client
                attempted = []

                def boundary(session, request, **kwargs):
                    attempted.append(request)
                    self.assertIn('/direct_v2/threads/broadcast/voice_attachment/', request.url)
                    if error is ClientIncompleteReadError:
                        raise requests.exceptions.ChunkedEncodingError('offline incomplete read')
                    response = requests.Response()
                    response.request = request
                    response.url = request.url
                    response.status_code = 408
                    response._content = b'{"status":"fail","message":"offline timeout"}'
                    return response

                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / 'offline.m4a'
                    path.write_bytes(b'offline fixture; upload is mocked')
                    with patch.object(client, 'user_id_from_username', return_value='456'), \
                         patch.object(client, '_direct_thread_id_from_user_ids', return_value=789), \
                         patch.object(client, '_voice_rupload', return_value=101), \
                         patch.object(sender, '_prepare_audio', return_value=path), \
                         patch('instagrapi.mixins.private.time.sleep'), \
                         patch.object(requests.Session, 'send', autospec=True, side_effect=boundary):
                        sender._send('offline_target', path)
                self.assertEqual(len(attempted), 1, 'Ambiguous broadcasts must never be replayed')
                self.assertIn(error.__name__, sender.state()['status'])
                self.assertIn('no automatic retry', sender.state()['status'])
                self.assertIsNone(sender.state()['message_id'])
                self.assertEqual(attempted[0].headers['Authorization'], client.authorization)
                self.assertIn('attachment_fbid=101', attempted[0].body)


if __name__ == '__main__':
    unittest.main()
