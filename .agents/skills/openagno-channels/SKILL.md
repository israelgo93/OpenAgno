---
name: openagno-channels
description: Use when connecting an OpenAgno agent to WhatsApp Cloud API (single-tenant or multi-tenant), WhatsApp QR via Baileys bridge, Slack, Telegram, AG-UI, or A2A. Covers webhook verification, signature validation, per-tenant credential encryption, and Meta Developer Console setup.
---

# OpenAgno channels skill

This skill covers the channel surface in OpenAgno. For the general-purpose runtime, read `.agents/skills/openagno/SKILL.md` first.

## Decision tree

```
Does the user run OpenAgno as a single operator account (self-hosting)?
├── Yes → Single-tenant. Use env vars and the Agno-provided /whatsapp/webhook.
└── No → Multi-tenant behind an external control plane.
        ├── Does the user want QR Link? → bridges/whatsapp-qr/ (Baileys, one session per tenant)
        └── Does the user want official Cloud API? → /whatsapp-cloud/{tenant_id}/webhook with AES-encrypted credentials
```

## WhatsApp Cloud API (single-tenant)

`.env` variables:

```bash
WHATSAPP_ACCESS_TOKEN=your_permanent_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_VERIFY_TOKEN=pick_any_long_random_string
WHATSAPP_APP_SECRET=your_app_secret   # optional but strongly recommended
```

`workspace/config.yaml`:

```yaml
channels:
  - whatsapp
whatsapp:
  mode: cloud_api        # or "dual" to also serve QR
```

Webhook: `GET/POST /whatsapp/webhook`. The runtime mounts the Agno `Whatsapp` interface that reads these env vars.

Meta Developer Console:

1. Open the App &gt; WhatsApp &gt; Configuration &gt; Webhook.
2. Callback URL: `https://your.public.domain/whatsapp/webhook`.
3. Verify Token: the exact value of `WHATSAPP_VERIFY_TOKEN`.
4. Subscribe to the `messages` field.

## WhatsApp Cloud API (multi-tenant)

Each tenant brings its own Meta credentials. An external control plane stores them AES-256-GCM encrypted in `public.whatsapp_cloud_channels` (Supabase). The runtime decrypts with the same `CHANNEL_SECRETS_KEY` and exposes a webhook per tenant.

Shared key setup (runs once):

```bash
# Generate on one machine
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"

# Set the SAME value on both sides
# OpenAgno runtime (.env)
CHANNEL_SECRETS_KEY=<the_generated_key>
# External writer (.env)
CHANNEL_SECRETS_KEY=<exactly_the_same_key>
```

If `CHANNEL_SECRETS_KEY` is missing at runtime startup, the multi-tenant router is not mounted. Startup log will say:

```
WhatsApp Cloud API multi-tenant desactivado: falta CHANNEL_SECRETS_KEY
```

Routes:

- `GET /whatsapp-cloud/{tenant_id}/webhook` &mdash; Meta verification. `tenant_id` is the `public.tenants.id` UUID. Compares `hub.verify_token` against the decrypted value and echoes `hub.challenge`. Writes `verified_at` on success.
- `POST /whatsapp-cloud/{tenant_id}/webhook` &mdash; Inbound event. Validates `X-Hub-Signature-256` with the tenant's `app_secret` (if set). Extracts `text` messages, resolves the agent via `TenantLoader`, runs it, and replies via Graph API `POST /{phone_number_id}/messages` with the tenant's `access_token`. Writes `last_event_at`, `last_send_at`, and `last_error` as the flow progresses.

Reference onboarding (implemented by whatever external control plane writes the encrypted row):

1. Tenant picks `cloud_api` or `dual` in the control plane's channel picker.
2. The control plane redirects to its own credentials form (for example, `/onboarding/whatsapp-cloud`).
3. Tenant pastes `phoneNumberId`, `accessToken`, optional `wabaId` and `appSecret`.
4. Optional "Test token" action calls Graph API `GET /{phone_number_id}?fields=id,display_phone_number,verified_name,quality_rating`.
5. On save, the control plane encrypts and persists the credentials, then displays the Callback URL and freshly generated Verify Token for the tenant to paste in Meta Developer Console.

## WhatsApp QR Link (Baileys bridge)

`workspace/config.yaml`:

```yaml
whatsapp:
  mode: qr_link
  qr_link:
    bridge_url: http://localhost:3001
```

Start the bridge:

```bash
cd bridges/whatsapp-qr
npm install
node index.js
# or: systemctl start openagno-whatsapp-bridge
```

Routes on the OSS gateway side:

- `GET /whatsapp-qr/status`
- `GET /whatsapp-qr/code` (HTML page with the QR)
- `GET /whatsapp-qr/code/json`
- `POST /whatsapp-qr/incoming` (the bridge posts inbound messages with `tenant_slug` in the body)

Bridge runtime (Node) exposes per-tenant routes on port 3001:

- `POST /sessions/{tenantSlug}` &mdash; create or restart a session
- `GET /sessions/{tenantSlug}/qr` &mdash; get the current QR as data URL
- `GET /sessions/{tenantSlug}/qr/image` &mdash; get the QR as PNG
- `POST /sessions/{tenantSlug}/send` &mdash; deliver an outbound text
- `POST /sessions/{tenantSlug}/restart` &mdash; restart and wipe creds
- `DELETE /sessions/{tenantSlug}` &mdash; wipe creds and memory

Handling rules baked into the bridge:

- `loggedOut` (401) and `replaced` persistent do NOT clear credentials automatically; they flip `needs_relink=true` and stop reconnecting until the customer explicitly hits "Re-vincular limpio".
- `restartRequired` (515) reconnects immediately without touching creds.
- `connection.update` close with a `replaced` event in the first 30 s after `connection=open` is treated as a ghost device on the customer's phone; they must close it manually.
- `/send` polls 500 ms &times; 4 for the socket before 503; failed sends go to an in-memory `pendingOutbox` (TTL 60 s) that drains on the next `connection=open`.

Common WhatsApp errors and remediation live in `docs/whatsapp-cloud-api.mdx`, `docs/channels.mdx`, and `docs/troubleshooting.mdx`.

## Slack, Telegram, AG-UI, A2A

- Slack: `SLACK_TOKEN`, `SLACK_SIGNING_SECRET` in `.env`, `channels: [slack]` in `config.yaml`.
- Telegram: `TELEGRAM_TOKEN` in `.env`, `channels: [telegram]`.
- AG-UI: `openagno add agui` (requires `[protocols]` extras).
- A2A: `a2a.enabled: true` (requires `[protocols]` extras).

## Debugging tips

- Always inspect `GET /admin/health` first. It reports active channels, agents, and model.
- For single-tenant WhatsApp, verify the webhook signature path with a local tool (e.g. `curl` with a stub Meta payload) before sending live traffic.
- For multi-tenant Cloud API, `GET /whatsapp-cloud/<unknown-uuid>/webhook` must return 404 `tenant_not_configured`. Anything else indicates the router is not mounted or the DB connection is broken.
- For QR Link, `curl http://localhost:3001/sessions` reports every active bridge session with `status`, `has_qr`, `needs_relink`, `last_error_code`, `last_connected_at`, and `pending_outbox`.
