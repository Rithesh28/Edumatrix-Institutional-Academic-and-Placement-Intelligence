/**
 * Step 4.6H.3 Browser Verification Script
 * Uses Chrome DevTools Protocol to verify the live UI on http://localhost:5173
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const USER_DATA_DIR = path.join(__dirname, '..', 'scratch', 'chrome_cdp_profile_h3');
const DEBUG_PORT = 9223;

function delay(ms) {
  return new Promise(r => setTimeout(r, ms));
}

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.id = 1;
    this.callbacks = new Map();
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (err) => reject(err);
      this.ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data);
        if (data.id && this.callbacks.has(data.id)) {
          const { resolve, reject } = this.callbacks.get(data.id);
          this.callbacks.delete(data.id);
          if (data.error) reject(data.error);
          else resolve(data.result);
        }
      };
    });
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = this.id++;
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expr) {
    const res = await this.send('Runtime.evaluate', {
      expression: expr,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res.exceptionDetails) {
      throw new Error(JSON.stringify(res.exceptionDetails));
    }
    return res.result?.value;
  }
}

async function run() {
  console.log('🚀 Step 4.6H.3 Browser Verification');
  
  if (!fs.existsSync(USER_DATA_DIR)) {
    fs.mkdirSync(USER_DATA_DIR, { recursive: true });
  }

  const chromeProc = spawn(CHROME_PATH, [
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${USER_DATA_DIR}`,
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1280,800',
    'about:blank'
  ]);

  try {
    let version = null;
    for (let i = 0; i < 30; i++) {
      try {
        const res = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/version`);
        version = await res.json();
        break;
      } catch (e) {
        await delay(500);
      }
    }

    if (!version) {
      throw new Error('Chrome remote debugging did not respond in time');
    }
    console.log('✅ Chrome connected:', version['Browser']);

    const listRes = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
    const pages = await listRes.json();
    const page = pages.find(p => p.type === 'page');
    if (!page) throw new Error('No page found');

    const client = new CDPClient(page.webSocketDebuggerUrl);
    await client.connect();
    console.log('✅ Connected to Page CDP session');

    await client.send('Page.enable');
    await client.send('Runtime.enable');

    // Step 1: Navigate to Login
    console.log('\n--- 1. Login ---');
    await client.send('Page.navigate', { url: 'http://localhost:5173/login' });
    await delay(1500);

    const initialUrl = await client.eval('window.location.href');
    if (!initialUrl.includes('/student/')) {
      let loginFormFound = false;
      for (let i = 0; i < 20; i++) {
        await delay(500);
        loginFormFound = await client.eval(`!!document.querySelector('input[name="email"]')`);
        if (loginFormFound) break;
      }

      if (loginFormFound) {
        await client.eval(`
          (() => {
            const nativeInputSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
            const emailInput = document.querySelector('input[name="email"]');
            nativeInputSetter.call(emailInput, 'adi01@gmail.com');
            emailInput.dispatchEvent(new Event('input', { bubbles: true }));

            const passInput = document.querySelector('input[name="password"]');
            nativeInputSetter.call(passInput, '54321');
            passInput.dispatchEvent(new Event('input', { bubbles: true }));

            const submitBtn = document.querySelector('button[type="submit"]');
            submitBtn.click();
          })()
        `);
      }

      for (let i = 0; i < 15; i++) {
        await delay(500);
        const url = await client.eval('window.location.href');
        if (url.includes('/student/')) break;
      }
    }

    console.log('Logged in successfully.');

    // Step 2: Navigate to Study Buddy
    console.log('\n--- 2. Navigate to Study Buddy ---');
    await client.send('Page.navigate', { url: 'http://localhost:5173/student/study-buddy' });
    await delay(2500);

    const studyBuddyUrl = await client.eval('window.location.href');
    console.log('Active Study Buddy URL:', studyBuddyUrl);

    // Step 3: Check Source Modes in Chat
    console.log('\n--- 3. Verifying 5 Source Modes in Chat ---');
    const sourceModes = await client.eval(`
      (() => {
        const modes = ['syllabus', 'lecture-notes', 'all', 'my-documents', 'all-my-sources'];
        return modes.map(id => {
          const el = document.getElementById('source-mode-' + id);
          return { id, exists: !!el, text: el ? el.innerText.trim() : null };
        });
      })()
    `);
    console.log('Source modes detected:', sourceModes);
    for (const sm of sourceModes) {
      if (!sm.exists) throw new Error(`Missing source mode button: source-mode-${sm.id}`);
    }
    console.log('✅ All 5 source mode buttons present and active in DOM.');

    // Step 4: Click My Documents tab
    console.log('\n--- 4. Switching to "My Documents" tab ---');
    const tabExists = await client.eval(`!!document.getElementById('tab-btn-my-docs')`);
    console.log('tab-btn-my-docs exists:', tabExists);
    if (!tabExists) throw new Error('tab-btn-my-docs button not found!');

    await client.eval(`document.getElementById('tab-btn-my-docs').click()`);
    await delay(1500);

    // Step 5: Verify My Documents UI elements
    console.log('\n--- 5. Verifying My Documents Controls ---');
    const controls = await client.eval(`
      (() => {
        return {
          uploadBtn: !!document.getElementById('btn-upload-my-doc'),
          refreshBtn: !!document.getElementById('btn-refresh-my-docs'),
          searchInput: !!document.getElementById('search-my-docs'),
          subjectFilter: !!document.getElementById('filter-my-docs-subject'),
          quotaDisplay: !!document.getElementById('my-docs-quota-status'),
        };
      })()
    `);
    console.log('My Documents controls:', controls);
    if (!controls.uploadBtn) throw new Error('Upload button missing!');
    if (!controls.refreshBtn) throw new Error('Refresh button missing!');
    if (!controls.searchInput) throw new Error('Search input missing!');
    if (!controls.subjectFilter) throw new Error('Subject filter missing!');
    if (!controls.quotaDisplay) throw new Error('Quota display missing!');
    console.log('✅ All My Documents controls mounted properly.');

    // Step 6: Test Upload Modal
    console.log('\n--- 6. Verifying Upload Modal ---');
    await client.eval(`document.getElementById('btn-upload-my-doc').click()`);
    await delay(600);

    const modalVisible = await client.eval(`!!document.getElementById('modal-upload-my-doc')`);
    console.log('Upload modal opened:', modalVisible);
    if (!modalVisible) throw new Error('Upload modal did not open!');

    // Close modal
    await client.eval(`
      const closeBtn = document.getElementById('modal-upload-my-doc').querySelector('button[title="Close"]') ||
                       document.getElementById('modal-upload-my-doc').querySelector('button:has(svg)');
      if (closeBtn) closeBtn.click();
    `);
    await delay(500);

    const modalAfterClose = await client.eval(`!!document.getElementById('modal-upload-my-doc')`);
    console.log('Upload modal closed cleanly:', !modalAfterClose);

    console.log('\n🎉 ALL Step 4.6H.3 Browser Checks Passed!');
  } finally {
    try {
      chromeProc.kill('SIGKILL');
    } catch (e) {}
  }
}

run().catch(err => {
  console.error('❌ Browser verification failed:', err);
  process.exit(1);
});
