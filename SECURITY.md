# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.3.x   | Yes       |
| 1.2.x   | Yes       |
| < 1.2   | No        |

## Reporting a vulnerability

Do not open public GitHub issues for security vulnerabilities.

Send reports to `security@datatensei.com` with:

- a description of the issue
- steps to reproduce
- potential impact
- any proof-of-concept material you can share safely

We will acknowledge receipt within 72 hours and follow up with remediation guidance or a fix timeline.

## Secrets and credentials

- Keep all secrets out of version control. `.env` is gitignored; use `.env.example` for the shape only.
- WhatsApp Cloud API multi-tenant credentials (Access Token, Verify Token, App Secret) are stored AES-256-GCM encrypted in Supabase. The master key (`CHANNEL_SECRETS_KEY`) is a 32-byte value shared between OpenAgno OSS and OpenAgnoCloud. Do not check it in, do not log it, and rotate it only as part of a coordinated re-encryption of existing rows.
- `WHATSAPP_SKIP_SIGNATURE_VALIDATION=true` exists for local development only. Never set it in production.
- API keys (`OPENAGNO_API_KEY`) should be generated with `openssl rand -hex 32` and kept unique per deployment.

## Dependencies

We track known vulnerabilities in our Python dependencies through standard scanners. Pull requests that bump a dependency for a security advisory should reference the advisory ID in the commit message.
