/**
 * Baileys WhatsApp sidecar for ARA (port 8767)
 *
 * Replace Playwright-based WhatsApp manager with direct WebSocket protocol.
 * Key decisions:
 *  - Separate Node.js process (decouples from Python server restarts)
 *  - Auth persisted to disk via useMultiFileAuthState
 *  - Inbound messages forwarded to Python via POST webhook
 *  - Auto-reconnects on disconnect (unless logged out)
 *
 * Env vars:
 *  WA_SIDECAR_PORT   — HTTP port (default 8767)
 *  WA_AUTH_DIR       — auth info directory
 *  ARA_INBOUND_URL   — Python server inbound webhook URL
 */

const express = require('express');
const { makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion, makeCacheableSignalKeyStore } = require('@whiskeysockets/baileys');
const QRCode = require('qrcode');
const { Boom } = require('@hapi/boom');
const path = require('path');
const fs = require('fs');
const http = require('http');
const P = require('pino');

const ARA_INBOUND_URL = process.env.ARA_INBOUND_URL || 'http://localhost:8766/api/whatsapp/inbound';
const PORT = parseInt(process.env.WA_SIDECAR_PORT || '8767');
const AUTH_DIR = process.env.WA_AUTH_DIR || path.join(__dirname, 'auth_info');
const SOCKET_TIMEOUT_MS = parseInt(process.env.WA_SOCKET_TIMEOUT || '60000');

let sock = null;
let qrBase64 = null;
let connectionState = 'disconnected';
let lastError = null;
let reconnectTimer = null;

fs.mkdirSync(AUTH_DIR, { recursive: true });

const logger = P({ level: 'warn', transport: { target: 'pino/file', options: { destination: 1 } } });

async function startSocket() {
  if (sock) {
    try { sock.end(); } catch (e) {}
    sock = null;
  }

  try {
    const { version, isLatest } = await fetchLatestBaileysVersion();
    logger.info(`Using WA version: ${version.join('.')}, isLatest: ${isLatest}`);

    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

    qrBase64 = null;
    connectionState = 'connecting';

    sock = makeWASocket({
      version, logger, printQRInTerminal: false,
      auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
      defaultQueryTimeoutMs: undefined,
      keepAliveIntervalMs: 30000,
      markOnlineOnConnect: true,
      syncFullHistory: false,
      generateHighQualityLinkPreview: false,
      emitOwnEvents: false,
      browser: ['ARA WhatsApp', 'Chrome', '125.0.0.0'],
    });

    sock.ev.on('creds.update', async () => { await saveCreds(); });

    sock.ev.on('qr', async (qr) => {
      try {
        qrBase64 = await QRCode.toDataURL(qr, { type: 'png', width: 300, margin: 2 });
        qrBase64 = qrBase64.replace(/^data:image\/png;base64,/, '');
        connectionState = 'awaiting_scan';
        logger.info('QR code generated, awaiting scan...');
      } catch (e) { logger.error(`QR generation failed: ${e.message}`); }
    });

    sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
      if (qr && !qrBase64) {
        try {
          qrBase64 = await QRCode.toDataURL(qr, { type: 'png', width: 300, margin: 2 });
          qrBase64 = qrBase64.replace(/^data:image\/png;base64,/, '');
          connectionState = 'awaiting_scan';
        } catch (e) {}
      }
      if (connection === 'open') {
        connectionState = 'connected'; qrBase64 = null; lastError = null;
        logger.info('WhatsApp connected!');
      } else if (connection === 'close') {
        const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
        connectionState = 'disconnected';
        lastError = lastDisconnect?.error?.message || 'connection closed';
        logger.warn(`WhatsApp disconnected: ${lastError}. Reconnect: ${shouldReconnect}`);
        if (shouldReconnect) {
          if (reconnectTimer) clearTimeout(reconnectTimer);
          reconnectTimer = setTimeout(() => { logger.info('Reconnecting...'); startSocket(); }, 5000);
        } else {
          logger.warn('Logged out. Clearing auth.');
          connectionState = 'logged_out';
          const files = fs.readdirSync(AUTH_DIR);
          for (const f of files) {
            if (f !== '.gitkeep') fs.rmSync(path.join(AUTH_DIR, f), { recursive: true, force: true });
          }
        }
      }
    });

    // ── Inbound messages → Python webhook ──
    sock.ev.on('messages.upsert', async ({ messages, type }) => {
      for (const msg of messages) {
        if (msg.key.fromMe) continue;
        if (!msg.message || msg.key.remoteJid.endsWith('@g.us')) continue;
        try {
          const phone = msg.key.remoteJid.replace('@s.whatsapp.net', '').replace(/[^0-9]/g, '');
          const pushName = msg.pushName || '';
          const text = msg.message?.conversation ||
            msg.message?.extendedTextMessage?.text ||
            msg.message?.imageMessage?.caption || '';
          if (!text || !phone) continue;
          logger.info(`Inbound from ${pushName || phone}: "${text.substring(0, 60)}..."`);
          const payload = JSON.stringify({ phone, name: pushName, message: text });
          const url = new URL(ARA_INBOUND_URL);
          const req = http.request({
            hostname: url.hostname, port: url.port, path: url.pathname,
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) },
          }, (res) => {
            let body = '';
            res.on('data', (chunk) => { body += chunk; });
            res.on('end', () => {
              if (res.statusCode !== 200) logger.warn(`ARA webhook ${res.statusCode}: ${body.substring(0, 100)}`);
            });
          });
          req.on('error', (e) => logger.warn(`ARA webhook error: ${e.message}`));
          req.write(payload);
          req.end();
        } catch (e) { logger.warn(`Inbound error: ${e.message}`); }
      }
    });
  } catch (e) {
    connectionState = 'error'; lastError = e.message;
    logger.error(`Socket error: ${e.message}`);
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => { logger.info('Retrying...'); startSocket(); }, 10000);
  }
}

async function sendMessage(phone, text) {
  if (!sock || connectionState !== 'connected') return { ok: false, error: `Not connected (${connectionState})` };
  try {
    let cleaned = phone.replace(/\D/g, '');
    if (!cleaned.startsWith('+') && cleaned.length === 10) cleaned = '91' + cleaned;
    const jid = `${cleaned}@s.whatsapp.net`;
    const result = await sock.sendMessage(jid, { text });
    return { ok: true, msgId: result?.key?.id || 'unknown' };
  } catch (e) {
    logger.error(`Send failed: ${e.message}`);
    return { ok: false, error: e.message };
  }
}

const app = express();
app.use(express.json());
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

app.get('/health', (req, res) => res.json({ status: 'ok', uptime: process.uptime() }));
app.get('/status', (req, res) => res.json({
  connected: connectionState === 'connected',
  authenticated: connectionState === 'connected',
  state: connectionState,
  message: connectionState === 'connected' ? 'Authenticated'
    : connectionState === 'awaiting_scan' ? 'Waiting for QR scan'
    : connectionState === 'connecting' ? 'Connecting...'
    : connectionState === 'logged_out' ? 'Logged out — need re-auth'
    : `Disconnected: ${lastError || 'unknown'}`,
}));
app.get('/qr', (req, res) => {
  if (qrBase64) res.type('text/plain').send(qrBase64);
  else res.status(404).type('text/plain').send('NOT_READY');
});
app.get('/link', (req, res) => { /* same HTML as Python's old /api/whatsapp/link */ res.send(`...see whatsapp-sidecar/index.js for full HTML...`); });
app.post('/send', async (req, res) => {
  const { phone, text } = req.body;
  if (!phone || !text) return res.status(400).json({ ok: false, error: 'phone and text required' });
  res.json(await sendMessage(phone, text));
});
app.get('/send', async (req, res) => {
  const { phone, text } = req.query;
  if (!phone || !text) return res.status(400).json({ ok: false, error: 'phone and text query params required' });
  res.json(await sendMessage(phone, text));
});

app.listen(PORT, () => {
  console.log(`WhatsApp sidecar listening on port ${PORT}`);
  startSocket();
});

process.on('SIGTERM', () => { if (sock) sock.end(); process.exit(0); });
process.on('SIGINT', () => { if (sock) sock.end(); process.exit(0); });
