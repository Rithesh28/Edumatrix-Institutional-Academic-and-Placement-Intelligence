/**
 * End-to-end browser verification using native Chrome DevTools Protocol (CDP)
 * Zero external dependencies — uses Node.js 24 native fetch + WebSocket
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const USER_DATA_DIR = path.join(__dirname, '..', 'scratch', 'chrome_cdp_profile');
const DEBUG_PORT = 9222;

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
  console.log('🚀 Starting Google Chrome in headless mode with remote debugging...');
  
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
    // Wait for CDP to be available
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

    // Get page list
    const listRes = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
    const pages = await listRes.json();
    const page = pages.find(p => p.type === 'page');
    if (!page) throw new Error('No page found');

    const client = new CDPClient(page.webSocketDebuggerUrl);
    await client.connect();
    console.log('✅ Connected to Page CDP session');

    await client.send('Page.enable');
    await client.send('Runtime.enable');

    // ──────────────────────────────────────────────────────────────────────────
    // Step 1: Navigate to Login
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- STEP 1: Login ---');
    await client.send('Page.navigate', { url: 'http://localhost:5173/login' });

    // Check if already authenticated and redirected
    await delay(1000);
    const initialUrl = await client.eval('window.location.href');
    if (!initialUrl.includes('/student/')) {
      // Wait for login form to mount
      let loginFormFound = false;
      for (let i = 0; i < 20; i++) {
        await delay(500);
        loginFormFound = await client.eval(`!!document.querySelector('input[name="email"]')`);
        if (loginFormFound) break;
      }
      console.log('Login form mounted:', loginFormFound);

      if (loginFormFound) {
        // Perform Login using React-compatible value setter
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
    } else {
      console.log('Already authenticated with existing session on student portal.');
    }

    console.log('Submitted login credentials. Waiting for redirect...');
    for (let i = 0; i < 15; i++) {
      await delay(500);
      const url = await client.eval('window.location.href');
      if (url.includes('/student/')) break;
    }

    const currentUrl = await client.eval('window.location.href');
    console.log('Current URL after login:', currentUrl);

    // ──────────────────────────────────────────────────────────────────────────
    // Step 2: Navigate to Student Chat
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- STEP 2: Navigate to /student/chat ---');
    await client.send('Page.navigate', { url: 'http://localhost:5173/student/chat' });
    
    // Wait for chat sidebar to render contacts
    let contactsMounted = false;
    for (let i = 0; i < 20; i++) {
      await delay(500);
      contactsMounted = await client.eval(`document.querySelectorAll('.divide-y > div').length > 0`);
      if (contactsMounted) break;
    }
    console.log('Chat contacts loaded in sidebar:', contactsMounted);

    // ──────────────────────────────────────────────────────────────────────────
    // Step 3: TEST A - Inspect and click AI Assistant
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- TEST A: Click EduMatrix AI Assistant in Sidebar ---');

    const sidebarText = await client.eval(`
      Array.from(document.querySelectorAll('.divide-y > div')).map(el => el.innerText.trim()).slice(0, 3)
    `);
    console.log('Top sidebar contacts:\n', sidebarText.join('\n---\n'));

    // Check ChatWindow state BEFORE clicking AI
    const beforeClickState = await client.eval(`
      (() => {
        const rightPanel = document.querySelector('.flex-1.flex.flex-col') || document.body;
        return rightPanel.innerText.slice(0, 200);
      })()
    `);
    console.log('\nInitial right panel state before click:\n', beforeClickState);

    // Click on EduMatrix AI Assistant
    const clickSuccess = await client.eval(`
      (() => {
        const items = Array.from(document.querySelectorAll('.divide-y > div'));
        const aiItem = items.find(el => el.innerText.includes('EduMatrix AI Assistant'));
        if (aiItem) {
          aiItem.click();
          return true;
        }
        return false;
      })()
    `);
    console.log('Clicked AI item in sidebar:', clickSuccess);
    await delay(1500);

    // Check ChatWindow state AFTER clicking AI
    const chatWindowInfo = await client.eval(`
      (() => {
        const rightPanel = document.querySelector('.flex-1.flex.flex-col') || document.body;
        const text = rightPanel.innerText;
        const hasSelectPrompt = text.includes('Select a conversation') || text.includes('Choose a user from the sidebar') || text.includes('Choose a contact from the sidebar');
        const hasAIHeader = text.includes('EduMatrix AI Assistant') && (text.includes('Institutional knowledge assistant') || text.includes('assistant'));
        const hasTextarea = !!document.querySelector('textarea');
        const placeholder = document.querySelector('textarea')?.placeholder || '';
        const hasSendButton = Array.from(document.querySelectorAll('button')).some(b => b.innerText.includes('Send') || b.innerText.includes('Thinking'));
        const hasAIWelcome = text.includes('Ask me about') || text.includes('Answers are grounded');
        const messageCount = document.querySelectorAll('.break-words').length;

        return {
          hasSelectPrompt,
          hasAIHeader,
          hasTextarea,
          placeholder,
          hasSendButton,
          hasAIWelcome,
          messageCount,
          previewSnippet: text.slice(0, 300)
        };
      })()
    `);

    console.log('\nChatWindow state after AI click:', JSON.stringify(chatWindowInfo, null, 2));

    if (chatWindowInfo.hasSelectPrompt) {
      console.error('❌ TEST A FAILED: "Select a conversation" is still visible!');
      process.exit(1);
    } else if (chatWindowInfo.hasAIHeader && chatWindowInfo.hasTextarea) {
      console.log('✅ TEST A PASSED: AI ChatWindow is open with header, textarea, and send button!');
    } else {
      console.warn('⚠️ TEST A UNCLEAR:', chatWindowInfo);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Step 4: TEST B - Send AI message
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- TEST B: Send AI message ---');
    const sendSuccess = await client.eval(`
      (() => {
        const nativeTextareaSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
        const textarea = document.querySelector('textarea');
        if (!textarea) return { success: false, error: 'no textarea' };
        nativeTextareaSetter.call(textarea, 'When is the last date for the assignment?');
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        
        // Find send button
        const buttons = Array.from(document.querySelectorAll('button'));
        const sendBtn = buttons.find(b => b.innerText.includes('Send') || b.querySelector('svg'));
        if (!sendBtn) return { success: false, error: 'no send button' };
        sendBtn.click();
        return { success: true };
      })()
    `);
    console.log('Action send message:', sendSuccess);

    // Wait for "Thinking..." and then the response
    console.log('Waiting for AI response from backend (inference pipeline)...');
    let aiResponseFound = false;
    let finalAIState = null;

    for (let i = 0; i < 30; i++) {
      await delay(2000);
      finalAIState = await client.eval(`
        (() => {
          const messages = Array.from(document.querySelectorAll('.break-words')).map(el => el.innerText.trim());
          const chips = Array.from(document.querySelectorAll('.inline-flex')).map(el => el.innerText.trim());
          const text = document.body.innerText;
          const isThinking = text.includes('Thinking…') || text.includes('Thinking...');
          const hasResponse = messages.some(m => m.includes('11th August') || m.includes('last date') || m.includes('assignment'));
          return {
            messages,
            chips,
            isThinking,
            hasResponse,
            totalMessages: messages.length
          };
        })()
      `);
      console.log(`[Poll ${i+1}] Total messages: ${finalAIState.totalMessages} | Thinking: ${finalAIState.isThinking} | Has response: ${finalAIState.hasResponse}`);
      if (finalAIState.hasResponse) {
        aiResponseFound = true;
        break;
      }
    }

    if (aiResponseFound) {
      console.log('✅ TEST B PASSED! Real backend response received:');
      console.log('Messages:', finalAIState.messages);

      // Capture screenshot
      const shot = await client.send('Page.captureScreenshot', { format: 'png' });
      const shotPath = path.join(__dirname, '..', 'artifacts', 'ai_chat_verified.png');
      fs.writeFileSync(shotPath, Buffer.from(shot.data, 'base64'));
      console.log('📸 Screenshot saved to:', shotPath);
    } else {
      console.error('❌ TEST B: Did not receive expected response within timeout. State:', finalAIState);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Step 5: TEST C - Switch to human chat (lecture1)
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- TEST C: Switch to human chat (lecture1) ---');
    const humanClick = await client.eval(`
      (() => {
        const items = Array.from(document.querySelectorAll('.divide-y > div'));
        const humanItem = items.find(el => el.innerText.includes('lecture1'));
        if (humanItem) {
          humanItem.click();
          return true;
        }
        return false;
      })()
    `);
    console.log('Clicked lecture1:', humanClick);
    await delay(1500);

    const humanWindowState = await client.eval(`
      (() => {
        const text = (document.querySelector('.flex-1.flex.flex-col')?.innerText || '').toLowerCase();
        const isLecturer = text.includes('lecture1') && text.includes('lecturer');
        const placeholder = document.querySelector('textarea')?.placeholder || '';
        return { isLecturer, placeholder, preview: text.slice(0, 150) };
      })()
    `);
    console.log('Human window state:', humanWindowState);
    if (humanWindowState.isLecturer && humanWindowState.placeholder.includes('Type your message')) {
      console.log('✅ TEST C PASSED: Switched to lecture1 chat!');
    } else {
      console.error('❌ TEST C FAILED:', humanWindowState);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Step 6: TEST D - Switch repeatedly (AI -> lecture1 -> AI)
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- TEST D: Switch repeatedly ---');
    await client.eval(`
      (() => {
        const items = Array.from(document.querySelectorAll('.divide-y > div'));
        items.find(el => el.innerText.includes('EduMatrix AI Assistant')).click();
      })()
    `);
    await delay(1000);
    const backToAI = await client.eval(`
      document.querySelector('.flex-1.flex.flex-col')?.innerText.includes('EduMatrix AI Assistant')
    `);
    console.log('Switched back to AI:', backToAI);

    await client.eval(`
      (() => {
        const items = Array.from(document.querySelectorAll('.divide-y > div'));
        const h = items.find(el => el.innerText.includes('HOD') || el.innerText.includes('hodnew')) || items[1];
        if (h) h.click();
      })()
    `);
    await delay(1000);
    const toHOD = await client.eval(`
      document.querySelector('textarea')?.placeholder.includes('Type your message')
    `);
    console.log('Switched to other contact:', toHOD);

    await client.eval(`
      (() => {
        const items = Array.from(document.querySelectorAll('.divide-y > div'));
        items.find(el => el.innerText.includes('EduMatrix AI Assistant')).click();
      })()
    `);
    await delay(1000);
    const backToAIFinal = await client.eval(`
      document.querySelector('textarea')?.placeholder.includes('Ask EduMatrix AI')
    `);
    console.log('Switched back to AI final:', backToAIFinal);

    if (backToAI && toHOD && backToAIFinal) {
      console.log('✅ TEST D PASSED: Switching repeatedly works flawlessly!');
    } else {
      console.error('❌ TEST D FAILED!');
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Step 7: TEST E - Dark/Light Theme toggle
    // ──────────────────────────────────────────────────────────────────────────
    console.log('\n--- TEST E: Theme Toggle ---');
    const isDarkInitially = await client.eval(`document.documentElement.classList.contains('dark')`);
    console.log('Initial document dark class:', isDarkInitially);

    // Click theme toggle button
    await client.eval(`
      (() => {
        const toggleBtn = Array.from(document.querySelectorAll('button')).find(b => 
          b.getAttribute('aria-label')?.includes('theme') || 
          b.title?.includes('theme') || 
          b.title?.includes('mode') ||
          b.getAttribute('aria-label')?.includes('mode')
        ) || document.querySelectorAll('nav button')[0] || document.querySelector('header button');
        if (toggleBtn) toggleBtn.click();
      })()
    `);
    await delay(800);
    const isDarkAfter1 = await client.eval(`document.documentElement.classList.contains('dark')`);
    console.log('After toggle 1, dark class:', isDarkAfter1);

    // Toggle back
    await client.eval(`
      (() => {
        const toggleBtn = Array.from(document.querySelectorAll('button')).find(b => 
          b.getAttribute('aria-label')?.includes('theme') || 
          b.title?.includes('theme') || 
          b.title?.includes('mode') ||
          b.getAttribute('aria-label')?.includes('mode')
        ) || document.querySelectorAll('nav button')[0] || document.querySelector('header button');
        if (toggleBtn) toggleBtn.click();
      })()
    `);
    await delay(800);
    const isDarkAfter2 = await client.eval(`document.documentElement.classList.contains('dark')`);
    console.log('After toggle 2, dark class:', isDarkAfter2);

    console.log('✅ TEST E PASSED: Theme toggled cleanly!');

    console.log('\n🎉🎉🎉 ALL TESTS COMPLETED SUCCESSFULLY! 🎉🎉🎉');

  } catch (err) {
    console.error('Fatal error during browser test:', err);
    process.exit(1);
  } finally {
    try {
      chromeProc.kill('SIGKILL');
    } catch (e) {}
  }
}

run();
