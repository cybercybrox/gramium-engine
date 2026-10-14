const { Client, LocalAuth } = require('whatsapp-web.js');

// ============================================
// GRAMIUM WHATSAPP CONFIGURATION
// ============================================

// International format: country code + phone number.
// Do not include the + symbol.
const PHONE_NUMBER = '263789379749';

// Keep this identifier unchanged between restarts.
const SESSION_ID = 'gramium-bot';

// Session storage directory.
// LocalAuth manages the authentication credentials here.
const SESSION_PATH = './.wwebjs_auth';

// ============================================
// WHATSAPP CLIENT
// ============================================

const client = new Client({
    authStrategy: new LocalAuth({
        clientId: SESSION_ID,
        dataPath: SESSION_PATH
    }),

    // Request pairing with a phone number instead of QR.
    pairWithPhoneNumber: {
        phoneNumber: PHONE_NUMBER,
        showNotification: true,
        intervalMs: 180000
    },

    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox'
        ]
    }
});

// ============================================
// PHONE-NUMBER PAIRING CODE
// ============================================

client.on('code', (code) => {
    console.log('\n========================================');
    console.log('       GRAMIUM WHATSAPP PAIRING');
    console.log('========================================');
    console.log('\nYour WhatsApp pairing code is:\n');
    console.log(`             ${code}`);
    console.log('\n========================================');
    console.log('Open WhatsApp on your phone.');
    console.log('Go to Linked Devices.');
    console.log('Select Link with phone number instead.');
    console.log('Enter the code displayed above.');
    console.log('========================================\n');
});

// ============================================
// CONNECTION EVENTS
// ============================================

client.on('authenticated', () => {
    console.log('Authentication successful.');
    console.log('Gramium credentials have been authenticated.');
});

client.on('ready', () => {
    console.log('\n========================================');
    console.log('  GRAMIUM WHATSAPP CONNECTED SUCCESSFULLY');
    console.log('========================================\n');

    console.log('Session ID:', SESSION_ID);
    console.log('Session storage:', SESSION_PATH);
    console.log('WhatsApp is ready.');
    console.log('The saved session can be reused after restart.');
});

client.on('auth_failure', (message) => {
    console.error('\nWhatsApp authentication failed.');
    console.error(message);
});

client.on('disconnected', (reason) => {
    console.log('\nWhatsApp disconnected:', reason);
});

client.on('loading_screen', (percent, message) => {
    console.log(`Loading WhatsApp: ${percent}% - ${message}`);
});

client.on('change_state', (state) => {
    console.log('WhatsApp connection state:', state);
});

// ============================================
// START GRAMIUM
// ============================================

async function startWhatsApp() {
    const normalizedNumber = PHONE_NUMBER.replace(/\D/g, '');

    if (!/^\d{8,15}$/.test(normalizedNumber)) {
        console.error('Invalid phone-number format.');
        process.exitCode = 1;
        return;
    }

    console.log('\n========================================');
    console.log('       STARTING GRAMIUM');
    console.log('========================================');

    console.log('Authentication: Phone-number pairing');
    console.log('QR display: Disabled');
    console.log('Session ID:', SESSION_ID);
    console.log('Session storage:', SESSION_PATH);

    try {
        await client.initialize();
    } catch (error) {
        console.error('\nCould not initialize WhatsApp.');
        console.error(error.message);
        process.exitCode = 1;
    }
}

// ============================================
// SHUTDOWN HANDLING
// ============================================

async function shutdown() {
    console.log('\nShutting down Gramium...');

    try {
        await client.destroy();
    } catch (error) {
        console.error('Shutdown message:', error.message);
    }

    process.exit(0);
}

process.once('SIGINT', shutdown);
process.once('SIGTERM', shutdown);

// ============================================
// RUN
// ============================================

startWhatsApp();
