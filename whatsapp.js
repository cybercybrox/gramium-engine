const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

// ============================================
// CONFIGURATION
// ============================================

// Enter your WhatsApp number with country code.
// Example format: 263771234567
// Do not include the + symbol.
const PHONE_NUMBER = '263789379749';

// Persistent session identifier.
// Keep this unchanged to reuse the same saved session.
const SESSION_ID = 'gramium-bot';

// ============================================
// WHATSAPP CLIENT
// ============================================

const client = new Client({
authStrategy: new LocalAuth({
clientId: SESSION_ID,
dataPath: './.wwebjs_auth'
}),

puppeteer: {
    headless: true,
    args: [
        '--no-sandbox',
        '--disable-setuid-sandbox'
    ]
}

});

// ============================================
// CONNECTION EVENTS
// ============================================

client.on('qr', (qr) => {
console.log('\nWhatsApp authentication QR code:\n');
qrcode.generate(qr, { small: true });

console.log(
    '\nOpen WhatsApp > Linked Devices > Link a Device.'
);

});

client.on('authenticated', () => {
console.log('Authentication successful!');
console.log('WhatsApp session authenticated.');
});

client.on('ready', () => {
console.log('\n================================');
console.log(' WHATSAPP CONNECTED SUCCESSFULLY');
console.log('================================\n');

console.log('Session ID:', SESSION_ID);
console.log('The saved session can be reused after restart.');

});

client.on('auth_failure', (message) => {
console.error('WhatsApp authentication failed:', message);
});

client.on('disconnected', (reason) => {
console.log('WhatsApp disconnected:', reason);
});

client.on('loading_screen', (percent, message) => {
console.log("Loading WhatsApp: ${percent}% - ${message}");
});

// ============================================
// START APPLICATION
// ============================================

async function startWhatsApp() {
const normalizedNumber = PHONE_NUMBER.replace(/\D/g, '');

if (
    !/^\d{8,15}$/.test(normalizedNumber) ||
    normalizedNumber === '263YOURNUMBER'
) {
    console.error(
        'Please replace PHONE_NUMBER with your real number.'
    );
    process.exitCode = 1;
    return;
}

console.log('Starting Gramium WhatsApp client...');
console.log('Configured phone number:', normalizedNumber);
console.log('Session identifier:', SESSION_ID);
console.log('Session storage: ./.wwebjs_auth');

try {
    await client.initialize();
} catch (error) {
    console.error(
        'Could not initialize WhatsApp:',
        error.message
    );

    process.exitCode = 1;
}

}

startWhatsApp();
