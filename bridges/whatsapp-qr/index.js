const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, Browsers } = require('@whiskeysockets/baileys');
const express = require('express');
const QRCode = require('qrcode');
const pino = require('pino');

const app = express();
app.use(express.json());

const GATEWAY_URL = process.env.GATEWAY_URL || 'http://localhost:8000';
const SESSION_DIR = process.env.SESSION_DIR || './session';
const PORT = process.env.BRIDGE_PORT || 3001;
const MAX_RETRIES = 5;

const logger = pino({ level: process.env.LOG_LEVEL || 'warn' });

let sock = null;
let currentQR = null;
let connectionStatus = 'disconnected';
let retryCount = 0;

async function connectWhatsApp() {
	if (retryCount >= MAX_RETRIES) {
		console.log(`Maximo de reintentos (${MAX_RETRIES}) alcanzado. Reinicia el bridge manualmente.`);
		connectionStatus = 'max_retries';
		return;
	}

	const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);

	sock = makeWASocket({
		auth: state,
		browser: Browsers.ubuntu('Chrome'),
		logger: logger,
	});

	sock.ev.on('creds.update', saveCreds);

	sock.ev.on('connection.update', (update) => {
		const { connection, lastDisconnect, qr } = update;

		if (qr) {
			currentQR = qr;
			connectionStatus = 'waiting_qr';
			retryCount = 0;
			console.log('QR generado - escanear desde WhatsApp > Dispositivos vinculados');
		}

		if (connection === 'open') {
			currentQR = null;
			connectionStatus = 'connected';
			retryCount = 0;
			console.log('WhatsApp conectado via QR');
		}

		if (connection === 'close') {
			const statusCode = lastDisconnect?.error?.output?.statusCode;
			const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
			connectionStatus = 'disconnected';

			if (shouldReconnect) {
				retryCount++;
				const delay = Math.min(retryCount * 2000, 10000);
				console.log(`Reconectando en ${delay / 1000}s (intento ${retryCount}/${MAX_RETRIES})...`);
				setTimeout(connectWhatsApp, delay);
			} else {
				console.log('Sesion cerrada (loggedOut). Limpia ./session y reinicia para nuevo QR.');
				connectionStatus = 'logged_out';
			}
		}
	});

	sock.ev.on('messages.upsert', async (upsert) => {
		const messages = upsert.messages || upsert;
		const msgArray = Array.isArray(messages) ? messages : [messages];

		for (const msg of msgArray) {
			if (!msg.message) continue;
			if (msg.key.fromMe) continue;
			if (msg.key.remoteJid === 'status@broadcast') continue;

			const jid = msg.key.remoteJid;
			const text = msg.message?.conversation
				|| msg.message?.extendedTextMessage?.text
				|| msg.message?.imageMessage?.caption
				|| msg.message?.videoMessage?.caption
				|| '';

			console.log(`Mensaje de ${jid}: "${text.substring(0, 80)}"`);

			if (!text) {
				console.log(`  (sin texto, tipo: ${Object.keys(msg.message).join(', ')})`);
				continue;
			}

			try {
				const resp = await fetch(`${GATEWAY_URL}/whatsapp-qr/incoming`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						from: jid,
						text: text,
						message_id: msg.key.id,
						timestamp: msg.messageTimestamp,
					}),
				});
				const result = await resp.json();
				console.log(`  -> Gateway: ${JSON.stringify(result)}`);
			} catch (err) {
				console.error(`  -> Error reenviando: ${err.message}`);
			}
		}
	});
}

app.get('/status', (req, res) => {
	res.json({ status: connectionStatus, has_qr: !!currentQR, retries: retryCount });
});

app.get('/qr', async (req, res) => {
	if (!currentQR) {
		return res.json({ status: connectionStatus, qr: null });
	}
	const qrDataUrl = await QRCode.toDataURL(currentQR);
	res.json({ status: 'waiting_qr', qr: qrDataUrl });
});

app.get('/qr/image', async (req, res) => {
	if (!currentQR) {
		return res.status(404).json({ error: 'QR no disponible', status: connectionStatus });
	}
	const qrBuffer = await QRCode.toBuffer(currentQR, { width: 300, margin: 2 });
	res.type('image/png').send(qrBuffer);
});

app.post('/send', async (req, res) => {
	const { to, text } = req.body;
	if (!sock || connectionStatus !== 'connected') {
		return res.status(503).json({ error: 'WhatsApp no conectado' });
	}
	try {
		// Si el JID ya contiene @ (formato completo), usarlo directo
		const jid = to.includes('@') ? to : `${to}@s.whatsapp.net`;
		await sock.sendMessage(jid, { text });
		console.log(`Respuesta enviada a ${jid}: "${text.substring(0, 50)}..."`);
		res.json({ status: 'sent' });
	} catch (err) {
		console.error(`Error enviando a ${to}: ${err.message}`);
		res.status(500).json({ error: err.message });
	}
});

app.post('/restart', (req, res) => {
	retryCount = 0;
	connectionStatus = 'disconnected';
	if (sock) {
		try { sock.end(); } catch (e) { /* ignore */ }
	}
	connectWhatsApp();
	res.json({ status: 'restarting' });
});

app.listen(PORT, () => {
	console.log(`WhatsApp QR Bridge en puerto ${PORT}`);
	connectWhatsApp();
});
