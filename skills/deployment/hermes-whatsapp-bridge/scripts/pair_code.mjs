import { makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion } from '@whiskeysockets/baileys'
import pino from 'pino'

// Pairing-code flow for the Hermes WhatsApp bridge.
// Usage: node pair_code.mjs <session-dir> <phone-without-plus>
// Prints PAIRING_CODE=<8 chars>; Greg types it on the phone
// (Linked devices → Link a device → Link with phone number).
// Keep the process alive until the phone entry completes (creds persist via saveCreds).

const sessionDir = process.argv[2] || '/opt/whatsapp-bridge/session'
const phone = process.argv[3] || '919582549236'

const { state, saveCreds } = await useMultiFileAuthState(sessionDir)
const { version } = await fetchLatestBaileysVersion().catch(() => ({}))
const logger = pino({ level: 'silent' })
const sock = makeWASocket({
  auth: state,
  ...(version ? { version } : {}),
  logger,
  browser: ['Hermes Agent', 'Chrome', '120.0'],
  printQRInTerminal: false,
  markOnlineOnConnect: false,
  syncFullHistory: false,
})
sock.ev.on('creds.update', () => { saveCreds(); })
sock.ev.on('connection.update', (u) => {
  console.log('conn:', u.connection, u.lastDisconnect?.error ? 'REASON:' + JSON.stringify(u.lastDisconnect.error) : '')
  if (u.qr) console.log('QR_PRESENT')
  if (u.connection === 'open') console.log('LINKED_OK')
})

// requestPairingCode needs the socket open; the first attempt often races the
// connect and fails with 'Connection Closed', so retry.
let code = null
for (let i = 0; i < 10; i++) {
  try {
    code = await sock.requestPairingCode(phone)
    break
  } catch (err) {
    console.log('retry', i, err.message)
    await new Promise(r => setTimeout(r, 2500))
  }
}
if (code) {
  console.log('PAIRING_CODE=' + code)
} else {
  console.log('PAIRING_FAILED')
}
// Keep alive so the link can complete and creds persist.
setInterval(() => {}, 5000)
