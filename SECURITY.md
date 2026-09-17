# Security

## Keep account data private

`ig_session.json` contains authentication credentials. Never commit it, include it in bug reports, upload it to a paste service, or distribute it with a build. Local microphone recordings and logs may also contain sensitive information.

The application is a local desktop tool, not a multi-user server. Do not expose its local web interface or bridge to a network. Only run source and dependencies you trust.

## Reporting a vulnerability

Do not open a public issue containing secrets or exploit details. Use this repository's private vulnerability reporting feature when available, or contact the maintainer privately through their GitHub profile. A minimal description with no account data is sufficient to start.

If a cookie or session file is exposed, revoke the affected Instagram session through account security settings. Deleting a Git commit alone does not revoke credentials.

## Expected behavior

- No automatic sends on startup.
- Every send requires explicit recipient/file confirmation.
- No automatic retry after an ambiguous delivery result.
- A receipt proves API acceptance, not delivery or playback on another device.
- No session material in error messages, screenshots, test fixtures, or commits.
