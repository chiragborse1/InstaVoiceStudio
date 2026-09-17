"""Single-attempt instagrapi client for explicitly requested account operations.

Keep this small override aligned with the pinned instagrapi private_request:
retain auth, delay, counting and the low-level signing/header/response machinery,
but never enter its retry or automatic challenge-resolution branches.
"""
import logging

from instagrapi import Client
from instagrapi.mixins.private import random_delay


class SafeClient(Client):
    def __init__(self, **kwargs):
        # Silence only this dependency's module loggers: some fallback methods
        # bypass instance loggers and emit raw exception chains. Application and
        # root logging remain untouched. instagrapi is imported above.
        for name, logger in list(logging.Logger.manager.loggerDict.items()):
            if (name == 'instagrapi' or name.startswith('instagrapi.')) and isinstance(logger, logging.Logger):
                logger.disabled = True
        # request_log and public requests also use separate instance loggers.
        quiet = logging.Logger('instavoice.private', level=logging.CRITICAL + 1)
        quiet.addHandler(logging.NullHandler())
        quiet.propagate = False
        quiet.disabled = True
        self.private_request_logger = quiet
        self.public_request_logger = quiet
        kwargs['logger'] = quiet
        kwargs.update(session_retry_total=0, session_retry_backoff_factor=0,
                      session_retry_statuses=[], public_request_retries_count=1)
        super().__init__(**kwargs)

    def set_retry_config(self, **kwargs):
        # init/load_settings calls this again: saved defaults must not undo policy.
        kwargs.update(session_retry_total=0, session_retry_backoff_factor=0,
                      session_retry_statuses=[], public_request_retries_count=1)
        return super().set_retry_config(**kwargs)

    def private_request(self, endpoint, data=None, params=None, login=False,
                        with_signature=True, headers=None, extra_sig=None, domain=None):
        headers = dict(headers or {})
        if self.authorization and not any(key.lower() == 'authorization' for key in headers):
            headers['Authorization'] = self.authorization
        if self.delay_range:
            random_delay(delay_range=self.delay_range)
        self.private_requests_count += 1
        return self._send_private_request(
            endpoint, data=data, params=params, login=login,
            with_signature=with_signature, headers=headers or None,
            extra_sig=extra_sig, domain=domain,
        )
