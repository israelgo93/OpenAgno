const {
	default: makeWASocket,
	useMultiFileAuthState,
	DisconnectReason,
	Browsers,
	fetchLatestBaileysVersion,
	downloadMediaMessage,
} = require('@whiskeysockets/baileys');
const express = require('express');
const QRCode = require('qrcode');
const qrcodeTerminal = require('qrcode-terminal');
const pino = require('pino');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(express.json({ limit: '25mb' }));

process.on('unhandledRejection', (err) => {
	console.error('Error no capturado (promise):', err?.message || err);
});
process.on('uncaughtException', (err) => {
	console.error('Error no capturado (exception):', err?.message || err);
});

const GATEWAY_URL = process.env.GATEWAY_URL || 'http://localhost:8000';
const SESSION_DIR = path.resolve(process.env.SESSION_DIR || './session');
const PORT = Number(process.env.BRIDGE_PORT || 3001);
const MAX_RETRIES = 5;
const DEDUP_TTL_MS = 60_000;
const SLUG_REGEX = /^[a-z0-9][a-z0-9-]{0,63}$/;

const logger = pino({ level: process.env.LOG_LEVEL || 'warn' });

/**
 * Estado por tenant. Cada slug tiene su propia sesion Baileys aislada.
 * Map<string, SessionState>
 */
const sessions = new Map();

/**
 * Crea el estado inicial de una sesion.
 */
function createSessionState(slug) {
	return {
		slug,
		sock: null,
		currentQR: null,
		status: 'disconnected',
		retries: 0,
		processed: new Map(),
		connecting: false,
	};
}

function isValidSlug(raw) {
	if (typeof raw !== 'string') return false;
	const s = raw.toLowerCase();
	return SLUG_REGEX.test(s);
}

function normalizeSlug(raw) {
	if (!isValidSlug(raw)) return null;
	return raw.toLowerCase();
}

function sessionDirFor(slug) {
	return path.join(SESSION_DIR, slug);
}

function hasPersistedCreds(slug) {
	return fs.existsSync(path.join(sessionDirFor(slug), 'creds.json'));
}

function isProcessed(session, msgId) {
	if (!msgId) return false;
	if (session.processed.has(msgId)) return true;
	session.processed.set(msgId, Date.now());
	if (session.processed.size > 500) {
		const now = Date.now();
		for (const [id, ts] of session.processed) {
			if (now - ts > DEDUP_TTL_MS) session.processed.delete(id);
		}
	}
	return false;
}

function clearSessionDir(slug) {
	const dir = sessionDirFor(slug);
	if (fs.existsSync(dir)) {
		fs.rmSync(dir, { recursive: true, force: true });
	}
}

/**
 * Inicia o reinicia la conexion Baileys para un tenant.
 * Idempotente: si ya esta conectado, solo garantiza el estado y retorna.
 */
async function connectTenant(slug) {
	let session = sessions.get(slug);
	if (!session) {
		session = createSessionState(slug);
		sessions.set(slug, session);
	}
	if (session.connecting) return session;
	if (session.sock && session.status === 'connected') return session;

	if (session.retries >= MAX_RETRIES) {
		console.log(`[${slug}] Maximo de reintentos (${MAX_RETRIES}). Se requiere accion manual.`);
		session.status = 'max_retries';
		return session;
	}

	session.connecting = true;
	try {
		const { state, saveCreds } = await useMultiFileAuthState(sessionDirFor(slug));
		const { version } = await fetchLatestBaileysVersion();
		console.log(`[${slug}] Iniciando Baileys version WA ${version.join('.')}`);

		const sock = makeWASocket({
			version,
			auth: state,
			browser: Browsers.ubuntu('Chrome'),
			logger,
		});
		session.sock = sock;

		sock.ev.on('creds.update', saveCreds);

		sock.ev.on('connection.update', (update) => {
			const { connection, lastDisconnect, qr } = update;

			if (qr) {
				session.currentQR = qr;
				session.status = 'waiting_qr';
				session.retries = 0;
				console.log(`\n[${slug}] ESCANEA ESTE QR (WhatsApp > Dispositivos vinculados)`);
				qrcodeTerminal.generate(qr, { small: true }, (qrAscii) => {
					console.log(qrAscii);
				});
			}

			if (connection === 'open') {
				session.currentQR = null;
				session.status = 'connected';
				session.retries = 0;
				console.log(`[${slug}] WhatsApp conectado`);
			}

			if (connection === 'close') {
				const statusCode = lastDisconnect?.error?.output?.statusCode;
				const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
				session.status = 'disconnected';
				session.sock = null;

				if (shouldReconnect) {
					session.retries += 1;
					const delay = Math.min(session.retries * 2000, 10_000);
					console.log(`[${slug}] Reconectando en ${delay / 1000}s (intento ${session.retries}/${MAX_RETRIES})`);
					setTimeout(() => connectTenant(slug).catch((e) => console.error(`[${slug}] Reconexion fallo:`, e)), delay);
				} else {
					console.log(`[${slug}] Sesion cerrada (loggedOut). Limpiando y regenerando QR...`);
					session.status = 'logged_out';
					clearSessionDir(slug);
					session.retries = 0;
					setTimeout(() => connectTenant(slug).catch((e) => console.error(`[${slug}] Reconexion tras logout fallo:`, e)), 2000);
				}
			}
		});

		sock.ev.on('messages.upsert', async (upsert) => {
			if (upsert.type && upsert.type !== 'notify') return;

			const messages = upsert.messages || upsert;
			const msgArray = Array.isArray(messages) ? messages : [messages];

			for (const msg of msgArray) {
				if (!msg.message) continue;
				if (msg.key.fromMe) continue;
				if (msg.key.remoteJid === 'status@broadcast') continue;

				if (isProcessed(session, msg.key.id)) {
					console.log(`[${slug}] (omitido: mensaje duplicado ${msg.key.id})`);
					continue;
				}

				const jid = msg.key.remoteJid;
				const normalized =
					msg.message?.ephemeralMessage?.message ||
					msg.message?.viewOnceMessage?.message ||
					msg.message?.viewOnceMessageV2?.message ||
					msg.message?.documentWithCaptionMessage?.message ||
					msg.message;

				if (
					normalized?.protocolMessage ||
					normalized?.reactionMessage ||
					normalized?.editedMessage ||
					normalized?.pollCreationMessage ||
					normalized?.pollUpdateMessage ||
					normalized?.stickerMessage
				) {
					continue;
				}

				let text =
					normalized?.conversation ||
					normalized?.extendedTextMessage?.text ||
					normalized?.imageMessage?.caption ||
					normalized?.videoMessage?.caption ||
					'';

				let mediaData = null;
				let mimeType = null;
				let msgType = 'text';

				if (normalized?.audioMessage) {
					msgType = 'audio';
					mimeType = normalized.audioMessage.mimetype;
				} else if (normalized?.imageMessage) {
					msgType = 'image';
					mimeType = normalized.imageMessage.mimetype;
				} else if (normalized?.documentMessage) {
					msgType = 'document';
					mimeType = normalized.documentMessage.mimetype;
				}

				if (!text && msgType === 'text') {
					console.log(`[${slug}] (omitido: mensaje sin texto ni media soportada)`);
					continue;
				}

				if (msgType !== 'text') {
					try {
						console.log(`[${slug}] Descargando media tipo ${msgType}...`);
						const buffer = await downloadMediaMessage(msg, 'buffer', {}, { logger });
						mediaData = buffer.toString('base64');
						if (!text) text = `[Mensaje de ${msgType} recibido]`;
					} catch (err) {
						console.error(`[${slug}] Error descargando media:`, err.message);
						continue;
					}
				}

				console.log(`[${slug}] Mensaje de ${jid}: "${text.substring(0, 80)}" ${msgType !== 'text' ? '(media)' : ''}`);

				try {
					const resp = await fetch(`${GATEWAY_URL}/whatsapp-qr/incoming`, {
						method: 'POST',
						headers: {
							'Content-Type': 'application/json',
							'X-Tenant-ID': slug,
						},
						body: JSON.stringify({
							tenant_slug: slug,
							from: jid,
							text,
							type: msgType,
							mimeType,
							media: mediaData,
							message_id: msg.key.id,
							timestamp: msg.messageTimestamp,
						}),
					});
					const result = await resp.json();
					console.log(`[${slug}] -> Gateway: ${JSON.stringify(result)}`);
				} catch (err) {
					console.error(`[${slug}] -> Error reenviando: ${err.message}`);
				}
			}
		});
	} finally {
		session.connecting = false;
	}
	return session;
}

function describeSession(session) {
	return {
		tenant_slug: session.slug,
		status: session.status,
		has_qr: Boolean(session.currentQR),
		retries: session.retries,
	};
}

function ensureSessionOr404(req, res) {
	const slug = normalizeSlug(req.params.tenantSlug);
	if (!slug) {
		res.status(400).json({ error: 'invalid_tenant_slug' });
		return null;
	}
	let session = sessions.get(slug);
	if (!session) {
		session = createSessionState(slug);
		sessions.set(slug, session);
	}
	return { slug, session };
}

// ===== Endpoints por tenant (API nueva) =====

app.get('/sessions', (_req, res) => {
	const list = Array.from(sessions.values()).map(describeSession);
	res.json({ sessions: list, count: list.length });
});

app.post('/sessions/:tenantSlug', async (req, res) => {
	const slug = normalizeSlug(req.params.tenantSlug);
	if (!slug) return res.status(400).json({ error: 'invalid_tenant_slug' });
	try {
		const session = await connectTenant(slug);
		return res.json(describeSession(session));
	} catch (err) {
		return res.status(500).json({ error: err?.message || 'connect_failed' });
	}
});

app.get('/sessions/:tenantSlug/status', (req, res) => {
	const ctx = ensureSessionOr404(req, res);
	if (!ctx) return;
	res.json(describeSession(ctx.session));
});

app.get('/sessions/:tenantSlug/qr', async (req, res) => {
	const ctx = ensureSessionOr404(req, res);
	if (!ctx) return;
	const { session } = ctx;
	if (!session.currentQR) {
		return res.json({ status: session.status, qr: null });
	}
	const qrDataUrl = await QRCode.toDataURL(session.currentQR);
	res.json({ status: 'waiting_qr', qr: qrDataUrl });
});

app.get('/sessions/:tenantSlug/qr/image', async (req, res) => {
	const ctx = ensureSessionOr404(req, res);
	if (!ctx) return;
	const { session } = ctx;
	if (!session.currentQR) {
		return res.status(404).json({ error: 'no_qr_available', status: session.status });
	}
	const qrBuffer = await QRCode.toBuffer(session.currentQR, { width: 300, margin: 2 });
	res.type('image/png').send(qrBuffer);
});

app.post('/sessions/:tenantSlug/send', async (req, res) => {
	const ctx = ensureSessionOr404(req, res);
	if (!ctx) return;
	const { slug, session } = ctx;
	const { to, text } = req.body || {};
	if (!to || typeof text !== 'string') {
		return res.status(400).json({ error: 'missing_fields' });
	}
	if (!session.sock || session.status !== 'connected') {
		return res.status(503).json({ error: 'whatsapp_not_connected', status: session.status });
	}
	try {
		const jid = to.includes('@') ? to : `${to}@s.whatsapp.net`;
		await session.sock.sendMessage(jid, { text });
		console.log(`[${slug}] Respuesta enviada a ${jid}: "${text.substring(0, 50)}..."`);
		res.json({ status: 'sent' });
	} catch (err) {
		console.error(`[${slug}] Error enviando a ${to}: ${err.message}`);
		res.status(500).json({ error: err.message });
	}
});

app.post('/sessions/:tenantSlug/restart', async (req, res) => {
	const ctx = ensureSessionOr404(req, res);
	if (!ctx) return;
	const { slug, session } = ctx;
	session.retries = 0;
	session.status = 'disconnected';
	if (session.sock) {
		try { session.sock.end(); } catch { /* ignore */ }
	}
	clearSessionDir(slug);
	try {
		await connectTenant(slug);
		res.json({ status: 'restarting', ...describeSession(session) });
	} catch (err) {
		res.status(500).json({ error: err?.message || 'restart_failed' });
	}
});

app.delete('/sessions/:tenantSlug', async (req, res) => {
	const slug = normalizeSlug(req.params.tenantSlug);
	if (!slug) return res.status(400).json({ error: 'invalid_tenant_slug' });
	const session = sessions.get(slug);
	if (session?.sock) {
		try { await session.sock.logout(); } catch { /* ignore */ }
		try { session.sock.end(); } catch { /* ignore */ }
	}
	sessions.delete(slug);
	clearSessionDir(slug);
	res.json({ status: 'deleted', tenant_slug: slug });
});

// ===== Bootstrap =====

async function bootstrap() {
	if (!fs.existsSync(SESSION_DIR)) {
		fs.mkdirSync(SESSION_DIR, { recursive: true });
	}

	const persistedSlugs = [];
	for (const entry of fs.readdirSync(SESSION_DIR, { withFileTypes: true })) {
		if (!entry.isDirectory()) continue;
		const slug = normalizeSlug(entry.name);
		if (!slug) continue;
		if (hasPersistedCreds(slug)) persistedSlugs.push(slug);
	}

	for (const slug of persistedSlugs) {
		connectTenant(slug).catch((err) => console.error(`[${slug}] bootstrap fallo:`, err));
	}

	app.listen(PORT, () => {
		console.log(`WhatsApp QR Bridge multi-tenant en puerto ${PORT}`);
		console.log(`Sesiones a restaurar: ${persistedSlugs.join(', ') || '(ninguna)'}`);
	});
}

bootstrap();
