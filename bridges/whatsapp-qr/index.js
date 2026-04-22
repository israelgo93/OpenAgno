import makeWASocket, {
	useMultiFileAuthState,
	DisconnectReason,
	Browsers,
	fetchLatestBaileysVersion,
	downloadMediaMessage,
} from '@whiskeysockets/baileys';
import express from 'express';
import QRCode from 'qrcode';
import qrcodeTerminal from 'qrcode-terminal';
import pino from 'pino';
import fs from 'fs';
import path from 'path';

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
const OUTBOX_TTL_MS = 60_000;
const SEND_READY_POLL_INTERVAL_MS = 500;
const SEND_READY_POLL_ATTEMPTS = 4;
const REPLACED_EARLY_WINDOW_MS = 30_000;
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
		// Circuit breaker para conflicto 'replaced'. Cuando WhatsApp devuelve
		// DisconnectReason.connectionReplaced repetidas veces es sintoma de
		// otro dispositivo vinculado compitiendo (fantasma en el telefono).
		// Marcamos needsRelink y dejamos de reconectar, pero NO borramos
		// creds.json: solo el operador debe decidirlo via DELETE /sessions o
		// el CTA "Re-vincular limpio" del dashboard.
		replacedEvents: [],
		needsRelink: false,
		lastErrorCode: null,
		lastConnectedAt: null,
		lastRelinkReason: null,
		// Cola de respuestas pendientes. Cuando /send falla porque el socket
		// cayo entre que el agente produjo la respuesta y el HTTP call, la
		// encolamos con TTL y la drenamos al proximo connection === 'open'.
		pendingOutbox: [],
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
 * Cierra el socket de Baileys de forma segura, ignorando errores. Antes de
 * tocar creds.json en disco hay que llamarlo y darle un tick al event loop
 * para que no se solapen las escrituras de `creds.update` con nuestra limpieza.
 */
async function safeCloseSocket(sock) {
	if (!sock) return;
	try { sock.ev?.removeAllListeners?.('creds.update'); } catch { /* ignore */ }
	try { sock.end(); } catch { /* ignore */ }
	await new Promise((r) => setTimeout(r, 150));
}

/**
 * Limpieza explicita de creds: solo se llama desde endpoints que el operador
 * invoca conscientemente (DELETE /sessions/:slug, POST .../restart, o CTA
 * "Re-vincular limpio" del dashboard). NUNCA desde un handler de desconexion.
 */
async function safeClearSessionDir(slug, session) {
	if (session?.sock) {
		await safeCloseSocket(session.sock);
		session.sock = null;
	}
	clearSessionDir(slug);
}

function enqueuePending(session, jid, text) {
	const now = Date.now();
	session.pendingOutbox = session.pendingOutbox.filter((m) => now - m.ts < OUTBOX_TTL_MS);
	session.pendingOutbox.push({ jid, text, ts: now });
}

async function drainPendingOutbox(session) {
	if (!session.sock || session.status !== 'connected') return;
	const now = Date.now();
	const toSend = session.pendingOutbox.filter((m) => now - m.ts < OUTBOX_TTL_MS);
	session.pendingOutbox = [];
	for (const { jid, text } of toSend) {
		try {
			await session.sock.sendMessage(jid, { text });
			console.log(`[${session.slug}] Outbox drenada -> ${jid}: "${text.substring(0, 50)}..."`);
		} catch (err) {
			console.error(`[${session.slug}] Outbox fallo enviar a ${jid}: ${err.message}`);
		}
	}
}

async function waitForSocketReady(session) {
	for (let i = 0; i < SEND_READY_POLL_ATTEMPTS; i++) {
		if (session.sock && session.status === 'connected') return true;
		await new Promise((r) => setTimeout(r, SEND_READY_POLL_INTERVAL_MS));
	}
	return Boolean(session.sock && session.status === 'connected');
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
				session.replacedEvents = [];
				session.lastConnectedAt = Date.now();
				session.lastErrorCode = null;
				session.lastRelinkReason = null;
				console.log(`[${slug}] WhatsApp conectado`);
				drainPendingOutbox(session).catch((e) =>
					console.error(`[${slug}] Error drenando outbox:`, e?.message || e),
				);
			}

			if (connection === 'close') {
				const statusCode = lastDisconnect?.error?.output?.statusCode;
				session.status = 'disconnected';
				session.sock = null;
				session.lastErrorCode = statusCode ?? null;

				// 515 restartRequired: evento transitorio justo despues del pairing
				// o cambios de protocolo. SIEMPRE reconectar sin limpiar creds.
				if (statusCode === DisconnectReason.restartRequired) {
					session.retries = 0;
					console.log(`[${slug}] restartRequired (515). Reconectando sin limpiar creds.`);
					setTimeout(
						() => connectTenant(slug).catch((e) => console.error(`[${slug}] Reconexion tras 515 fallo:`, e)),
						500,
					);
					return;
				}

				// 'replaced' (440): otra sesion tomo las keys. Si es muy temprano
				// tras un 'open' (ventana de 30s) es sintoma de dispositivo fantasma
				// en el telefono del operador. Marcamos needsRelink directamente.
				if (statusCode === DisconnectReason.connectionReplaced) {
					const now = Date.now();
					const connectedRecently =
						session.lastConnectedAt && now - session.lastConnectedAt < REPLACED_EARLY_WINDOW_MS;
					session.replacedEvents = session.replacedEvents.filter(
						(t) => now - t < REPLACED_EARLY_WINDOW_MS,
					);
					session.replacedEvents.push(now);

					const persistent = session.replacedEvents.length >= 3;
					if (persistent || connectedRecently) {
						console.log(
							`[${slug}] Conflicto 'replaced' (${session.replacedEvents.length} en 30s, connectedRecently=${Boolean(connectedRecently)}). ` +
							'Marcando needs_relink SIN borrar creds. El operador debe: ' +
							'(1) abrir WhatsApp > Dispositivos vinculados y cerrar el dispositivo fantasma, ' +
							'(2) esperar ~5 min, (3) usar el CTA "Re-vincular limpio" (DELETE /sessions/:slug + POST /sessions/:slug).',
						);
						session.status = 'needs_relink';
						session.needsRelink = true;
						session.retries = 0;
						session.replacedEvents = [];
						session.lastRelinkReason = 'connection_replaced_ghost_device';
						return;
					}
					session.retries += 1;
					console.log(
						`[${slug}] Conflicto 'replaced' (${session.replacedEvents.length}/3 en 30s). ` +
						'Reintento en 2s sin limpiar creds.',
					);
					setTimeout(
						() => connectTenant(slug).catch((e) => console.error(`[${slug}] Reconexion fallo:`, e)),
						2000,
					);
					return;
				}

				// loggedOut (401): en Baileys 6.x este codigo aparece tanto cuando
				// WhatsApp cierra la sesion de verdad como en transitorios post-pairing.
				// NUNCA borramos creds automaticamente: marcamos needs_relink y
				// dejamos que el operador decida via dashboard (DELETE + CTA).
				if (statusCode === DisconnectReason.loggedOut) {
					console.log(
						`[${slug}] loggedOut (401) reportado. Marcando needs_relink SIN borrar creds. ` +
						'Si fue un cierre genuino desde WhatsApp, usa "Re-vincular limpio" desde el dashboard.',
					);
					session.status = 'needs_relink';
					session.needsRelink = true;
					session.retries = 0;
					session.lastRelinkReason = 'logged_out_reported';
					return;
				}

				session.retries += 1;
				if (session.retries > MAX_RETRIES) {
					console.log(`[${slug}] Maximo de reintentos (${MAX_RETRIES}) alcanzado. Marcando needs_relink.`);
					session.status = 'needs_relink';
					session.needsRelink = true;
					session.lastRelinkReason = `max_retries_statuscode_${statusCode ?? 'unknown'}`;
					return;
				}
				const delay = Math.min(session.retries * 2000, 10_000);
				console.log(`[${slug}] Reconectando en ${delay / 1000}s (intento ${session.retries}/${MAX_RETRIES}, status=${statusCode})`);
				setTimeout(() => connectTenant(slug).catch((e) => console.error(`[${slug}] Reconexion fallo:`, e)), delay);
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
		needs_relink: Boolean(session.needsRelink),
		last_error_code: session.lastErrorCode ?? null,
		last_connected_at: session.lastConnectedAt ?? null,
		last_relink_reason: session.lastRelinkReason ?? null,
		pending_outbox: session.pendingOutbox?.length ?? 0,
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
	// Si el tenant estaba bloqueado por circuit breaker de 'replaced',
	// resetea el flag: el usuario pide explicitamente re-vincular.
	const existing = sessions.get(slug);
	if (existing) {
		existing.needsRelink = false;
		existing.replacedEvents = [];
		existing.retries = 0;
	}
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
	// Si needs_relink esta activo NO encolamos: la respuesta no va a poder
	// drenarse nunca hasta intervencion manual. Devolvemos 503 explicito.
	if (session.needsRelink) {
		return res.status(503).json({ error: 'whatsapp_needs_relink', status: session.status });
	}
	const jid = to.includes('@') ? to : `${to}@s.whatsapp.net`;
	// Polling corto: si el socket acaba de caer y esta reconectando, dale
	// margen antes de fallar. Evita 503 falsos tras hiccups de red.
	const ready = await waitForSocketReady(session);
	if (!ready) {
		// Encolamos con TTL 60s para drenar al proximo 'open'.
		enqueuePending(session, jid, text);
		console.log(`[${slug}] Socket no listo (status=${session.status}); respuesta encolada en outbox.`);
		return res.status(202).json({ status: 'queued', queue_size: session.pendingOutbox.length });
	}
	try {
		await session.sock.sendMessage(jid, { text });
		console.log(`[${slug}] Respuesta enviada a ${jid}: "${text.substring(0, 50)}..."`);
		res.json({ status: 'sent' });
	} catch (err) {
		console.error(`[${slug}] Error enviando a ${to}: ${err.message}. Encolando en outbox.`);
		enqueuePending(session, jid, text);
		res.status(202).json({ status: 'queued_after_error', queue_size: session.pendingOutbox.length, error: err.message });
	}
});

app.post('/sessions/:tenantSlug/restart', async (req, res) => {
	const ctx = ensureSessionOr404(req, res);
	if (!ctx) return;
	const { slug, session } = ctx;
	session.retries = 0;
	session.status = 'disconnected';
	session.needsRelink = false;
	session.replacedEvents = [];
	session.lastErrorCode = null;
	session.lastRelinkReason = null;
	session.pendingOutbox = [];
	await safeClearSessionDir(slug, session);
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
		await safeCloseSocket(session.sock);
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
