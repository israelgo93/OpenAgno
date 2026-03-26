const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const express = require('express');
const QRCode = require('qrcode');

const app = express();
app.use(express.json());

const GATEWAY_URL = process.env.GATEWAY_URL || 'http://localhost:8000';
const SESSION_DIR = process.env.SESSION_DIR || './session';
const PORT = process.env.BRIDGE_PORT || 3001;

let sock = null;
let currentQR = null;
let connectionStatus = 'disconnected';

async function connectWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);

    sock = makeWASocket({
        auth: state,
        printQRInTerminal: true,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            currentQR = qr;
            connectionStatus = 'waiting_qr';
            console.log('QR code generado — escanear desde WhatsApp');
        }
        if (connection === 'open') {
            currentQR = null;
            connectionStatus = 'connected';
            console.log('WhatsApp conectado via QR');
        }
        if (connection === 'close') {
            const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
            connectionStatus = 'disconnected';
            if (shouldReconnect) {
                console.log('Reconectando...');
                connectWhatsApp();
            }
        }
    });

    // Reenviar mensajes entrantes al gateway de OpenAgno
    sock.ev.on('messages.upsert', async ({ messages }) => {
        for (const msg of messages) {
            if (msg.key.fromMe) continue;

            const from = msg.key.remoteJid.replace('@s.whatsapp.net', '');
            const text = msg.message?.conversation
                || msg.message?.extendedTextMessage?.text
                || '';

            if (!text) continue;

            try {
                // Enviar al gateway como si fuera un webhook de Meta
                await fetch(`${GATEWAY_URL}/whatsapp-qr/incoming`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        from: from,
                        text: text,
                        message_id: msg.key.id,
                        timestamp: msg.messageTimestamp,
                    }),
                });
            } catch (err) {
                console.error('Error reenviando al gateway:', err.message);
            }
        }
    });
}

// Endpoints del bridge
app.get('/status', (req, res) => {
    res.json({ status: connectionStatus, has_qr: !!currentQR });
});

app.get('/qr', async (req, res) => {
    if (!currentQR) {
        return res.json({ status: connectionStatus, qr: null });
    }
    const qrDataUrl = await QRCode.toDataURL(currentQR);
    res.json({ status: 'waiting_qr', qr: qrDataUrl });
});

app.post('/send', async (req, res) => {
    const { to, text } = req.body;
    if (!sock || connectionStatus !== 'connected') {
        return res.status(503).json({ error: 'WhatsApp no conectado' });
    }
    try {
        await sock.sendMessage(`${to}@s.whatsapp.net`, { text });
        res.json({ status: 'sent' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`WhatsApp QR Bridge en puerto ${PORT}`);
    connectWhatsApp();
});
