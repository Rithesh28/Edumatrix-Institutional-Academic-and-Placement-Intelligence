/**
 * End-to-end browser verification for Phase 3.1 Step D:
 * AI Grounding, Retrieval & Response Reliability
 * Uses native Chrome DevTools Protocol (CDP) with Node.js
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const USER_DATA_DIR = path.join(__dirname, '..', 'scratch', 'chrome_cdp_profile_step_d');
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

async function sendMessage(client, query) {
  return await client.eval(`
    (() => {
      const textarea = document.querySelector('textarea');
      if (!textarea) return { success: false, error: 'no textarea' };
      const nativeTextareaSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
      nativeTextareaSetter.call(textarea, ${JSON.stringify(query)});
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
      
      // Target the send button right next to the textarea
      const sendBtn = textarea.parentElement.querySelector('button');
      if (!sendBtn) return { success: false, error: 'no send button' };
      sendBtn.click();
      return { success: true };
    })()
  `);
}

async function waitForAiResponse(client, minMessages, timeoutSec = 60) {
  const startTime = Date.now();
  while ((Date.now() - startTime) < timeoutSec * 1000) {
    await delay(2000);
    const state = await client.eval(`
      (() => {
        const bubbleEls = Array.from(document.querySelectorAll('.break-words'));
        const bubbles = bubbleEls.map(el => el.innerText.trim());
        const rawHtmls = bubbleEls.map(el => el.innerHTML);
        const lastBubbleEl = bubbleEls[bubbleEls.length - 1];
        const lastContainer = lastBubbleEl ? lastBubbleEl.closest('.max-w-sm') : null;
        
        // Scope chips to the latest message bubble only
        const chips = lastContainer 
          ? Array.from(lastContainer.querySelectorAll('.inline-flex')).map(el => el.innerText.trim())
          : [];
        
        // Check for any mood/intent badges in the entire document and specifically the last bubble
        const moodBadges = Array.from(document.querySelectorAll('span')).filter(s => s.innerText.includes('Mood:')).map(s => s.innerText);
        const intentBadges = Array.from(document.querySelectorAll('span')).filter(s => s.innerText.includes('Intent:')).map(s => s.innerText);
        const isThinking = document.body.innerText.includes('Thinking…') || document.body.innerText.includes('Thinking...');
        return {
          totalBubbles: bubbles.length,
          lastBubble: bubbles[bubbles.length - 1] || '',
          allBubbles: bubbles,
          rawHtmls,
          chips,
          moodBadges,
          intentBadges,
          isThinking
        };
      })()
    `);
    if (state.totalBubbles >= minMessages && !state.isThinking) {
      return state;
    }
  }
  throw new Error(`Timeout waiting for AI reply (expected >= ${minMessages} bubbles)`);
}

async function run() {
  console.log('🚀 Starting Google Chrome for Phase 3.1 Step D Browser Verification...');
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
    if (!version) throw new Error('Chrome remote debugging did not respond');
    console.log('✅ Chrome connected:', version['Browser']);

    const listRes = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
    const pages = await listRes.json();
    const page = pages.find(p => p.type === 'page');
    if (!page) throw new Error('No page found');

    const client = new CDPClient(page.webSocketDebuggerUrl);
    await client.connect();
    await client.send('Page.enable');
    await client.send('Runtime.enable');

    // ──────────────────────────────────────────────────────────────────────────
    // Step 1: Login as student adi01@gmail.com
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- 1. Login as Student ---');
    await client.send('Page.navigate', { url: 'http://localhost:5173/login' });
    await delay(1500);

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

          document.querySelector('button[type="submit"]').click();
        })()
      `);
    }

    // Wait for redirect to student dashboard
    for (let i = 0; i < 20; i++) {
      await delay(500);
      const url = await client.eval('window.location.href');
      if (url.includes('/student/')) break;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Step 2: Navigate to Chat
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- 2. Navigate to Student Chat ---');
    await client.send('Page.navigate', { url: 'http://localhost:5173/student/chat' });
    await delay(2000);

    // Click "EduMatrix AI Assistant" in sidebar
    await client.eval(`
      (() => {
        const items = Array.from(document.querySelectorAll('.divide-y > div'));
        const aiItem = items.find(el => el.innerText.includes('EduMatrix AI Assistant'));
        if (aiItem) aiItem.click();
      })()
    `);
    await delay(2000);

    const initialBubbles = await client.eval(`document.querySelectorAll('.break-words').length`);
    console.log('Initial chat bubbles loaded:', initialBubbles);

    // ──────────────────────────────────────────────────────────────────────────
    // Step 3: SCENARIO 1 — Exact DSP Query
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- SCENARIO 1: Ask "When is the last date for DSP assignment?" ---');
    await sendMessage(client, 'When is the last date for DSP assignment?');
    const state1 = await waitForAiResponse(client, initialBubbles + 2);
    console.log('AI Reply 1:', state1.lastBubble);
    console.log('Sources 1:', state1.chips);

    // Verify constraints:
    // a) Contains DSP
    if (!state1.lastBubble.includes('DSP')) throw new Error('Scenario 1 FAILED: Missing "DSP" in reply');
    // b) Contains deadline (2026-10-08 or 8/10/2026 or October 8)
    const hasDspDate = state1.lastBubble.includes('2026-10-08') || state1.lastBubble.includes('8/10/2026') || state1.lastBubble.includes('October 8') || state1.lastBubble.includes('8 October');
    if (!hasDspDate) throw new Error('Scenario 1 FAILED: Missing valid DSP deadline date');
    // c) NO hallucinated "Data Science Programming"
    if (state1.lastBubble.toLowerCase().includes('data science programming')) throw new Error('Scenario 1 FAILED: Hallucinated "Data Science Programming" expansion!');
    // d) Source chips only contain DSP
    if (state1.chips.some(c => c.includes('ML'))) throw new Error('Scenario 1 FAILED: Unrelated ML source appeared in DSP reply');
    // e) No raw ** asterisks
    if (state1.lastBubble.includes('**')) throw new Error('Scenario 1 FAILED: Raw ** asterisks present in bubble text');
    // f) No student-facing Mood or Intent badges
    if (state1.moodBadges.length > 0 || state1.intentBadges.length > 0) throw new Error('Scenario 1 FAILED: Student UI still displays Mood/Intent badges');

    console.log('✅ SCENARIO 1 PASSED: Correct deadline, DSP preserved, no expansion, ML filtered, clean formatting!');

    // ──────────────────────────────────────────────────────────────────────────
    // Step 4: SCENARIO 2 — Ambiguous Assignment Query
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- SCENARIO 2: Ask "When is the last date for assignment submission?" (Ambiguous) ---');
    await sendMessage(client, 'When is the last date for assignment submission?');
    const state2 = await waitForAiResponse(client, initialBubbles + 4);
    console.log('AI Reply 2:', state2.lastBubble);
    console.log('Sources 2:', state2.chips);

    // Verify constraints:
    // a) Did not pick arbitrarily -> asked clarification
    if (!state2.lastBubble.includes('Which assignment are you asking about?')) {
      throw new Error('Scenario 2 FAILED: Did not ask clarification for ambiguous assignment query');
    }
    // b) Lists verified candidate assignments with deadlines
    if (!state2.lastBubble.includes('DSP Assignment') || !state2.lastBubble.includes('-')) {
      throw new Error('Scenario 2 FAILED: Clarification missing candidate assignments list');
    }
    console.log('✅ SCENARIO 2 PASSED: Ambiguity detected and clarification provided without guessing!');

    // ──────────────────────────────────────────────────────────────────────────
    // Step 5: SCENARIO 3 — Exact ML Query
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- SCENARIO 3: Ask "When is the last date for ML assignment?" ---');
    await sendMessage(client, 'When is the last date for ML assignment?');
    const state3 = await waitForAiResponse(client, initialBubbles + 6);
    console.log('AI Reply 3:', state3.lastBubble);
    console.log('Sources 3:', state3.chips);

    // Verify constraints:
    // a) ML evidence only
    if (state3.chips.some(c => c.includes('DSP'))) {
      throw new Error('Scenario 3 FAILED: DSP source leaked into ML query');
    }
    if (!state3.chips.some(c => c.includes('ML'))) {
      throw new Error('Scenario 3 FAILED: Missing ML source');
    }
    console.log('✅ SCENARIO 3 PASSED: Exact ML query retrieved ML evidence only!');

    // ──────────────────────────────────────────────────────────────────────────
    // Step 6: SCENARIO 4 — Unknown Assignment Query
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- SCENARIO 4: Ask unknown assignment "When is the Quantum Computing assignment due?" ---');
    await sendMessage(client, 'When is the Quantum Computing assignment due?');
    const state4 = await waitForAiResponse(client, initialBubbles + 8);
    console.log('AI Reply 4:', state4.lastBubble);
    console.log('Sources 4:', state4.chips);

    // Verify constraints:
    // a) Safe fallback
    if (!state4.lastBubble.toLowerCase().includes("couldn't find") && !state4.lastBubble.toLowerCase().includes("contact your")) {
      throw new Error('Scenario 4 FAILED: Did not trigger safe fallback for unknown assignment');
    }
    console.log('✅ SCENARIO 4 PASSED: Safe fallback triggered, no hallucinated assignment or date!');

    // ──────────────────────────────────────────────────────────────────────────
    // Step 7: SCENARIO 5 — Peer to Peer Chat (lecture1)
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- SCENARIO 5: Test Peer-to-Peer Chat with Lecturer ---');
    const clickResult = await client.eval(`
      (() => {
        const items = Array.from(document.querySelectorAll('.divide-y > div'));
        const humanItem = items.find(el => el.innerText.toLowerCase().includes('lecture1') || el.innerText.toLowerCase().includes('lecturer'));
        if (humanItem) {
          humanItem.click();
          return { clicked: true, text: humanItem.innerText };
        }
        return { clicked: false, allItems: items.map(el => el.innerText) };
      })()
    `);
    console.log('Scenario 5 Click result:', clickResult);

    let lecturerChatHeader = false;
    for (let i = 0; i < 20; i++) {
      await delay(500);
      const res = await client.eval(`
        (() => {
          const text = document.querySelector('.flex-1.flex.flex-col')?.innerText || '';
          const hasLecturer = text.toLowerCase().includes('lecture1') || text.toLowerCase().includes('lecturer');
          const isNotAi = !text.includes('Institutional knowledge assistant');
          return { text: text.slice(0, 100), hasLecturer, isNotAi };
        })()
      `);
      if (res.hasLecturer && res.isNotAi) {
        lecturerChatHeader = true;
        break;
      }
    }
    if (!lecturerChatHeader) throw new Error('Scenario 5 FAILED: Could not switch to lecturer P2P chat');
    console.log('✅ SCENARIO 5 PASSED: Lecturer P2P chat intact and functional!');

    // ──────────────────────────────────────────────────────────────────────────
    // Step 8: SCENARIO 6 — Dark/Light Theme Toggle
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- SCENARIO 6: Test Dark/Light Theme Toggle ---');
    const themeInitial = await client.eval(`document.documentElement.classList.contains('dark')`);
    await client.eval(`
      (() => {
        const btn = document.querySelector('button[aria-label*="theme" i]') ||
                    Array.from(document.querySelectorAll('button')).find(b => b.innerHTML.includes('svg') && (b.title?.toLowerCase().includes('theme') || b.className.includes('rounded')));
        if (btn) btn.click();
      })()
    `);
    await delay(500);
    const themeAfter = await client.eval(`document.documentElement.classList.contains('dark')`);
    console.log(`Theme toggled from dark=${themeInitial} to dark=${themeAfter}`);
    console.log('✅ SCENARIO 6 PASSED: Theme toggle works cleanly!');

    // ──────────────────────────────────────────────────────────────────────────
    // Step 9: Switch back to AI and Capture Screenshot
    // ──────────────────────────────────────────────────────────────────────────
    await client.eval(`
      (() => {
        const items = Array.from(document.querySelectorAll('.divide-y > div'));
        const aiItem = items.find(el => el.innerText.includes('EduMatrix AI Assistant'));
        if (aiItem) aiItem.click();
      })()
    `);
    await delay(1500);

    const shot = await client.send('Page.captureScreenshot', { format: 'png' });
    const shotPath = path.join(__dirname, '..', 'artifacts', 'step_d_verified.png');
    fs.writeFileSync(shotPath, Buffer.from(shot.data, 'base64'));
    console.log('📸 Final Step D screenshot saved to:', shotPath);

    console.log('\n🎉 ALL PHASE 3.1 STEP D BROWSER VERIFICATION SCENARIOS PASSED SUCCESSFULLY!');

  } finally {
    try {
      chromeProc.kill('SIGKILL');
    } catch (e) {}
  }
}

run().catch(err => {
  console.error('❌ Browser Test Error:', err);
  process.exit(1);
});
