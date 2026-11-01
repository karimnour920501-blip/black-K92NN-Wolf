/* Browser-side regression tests without network calls or third-party packages. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness() {
  const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
  assert.ok(script, 'inline application script exists');
  const elements = new Map();

  class FakeElement {
    constructor(id = '') {
      this.id = id;
      this.value = '';
      this.textContent = '';
      this.disabled = false;
      this.children = [];
      this.listeners = {};
      this.scrollHeight = 0;
      this.scrollTop = 0;
    }
    addEventListener(event, callback) { this.listeners[event] = callback; }
    appendChild(element) { this.children.push(element); }
    replaceChildren(...children) { this.children = children; }
  }

  function el(id) {
    if (!elements.has(id)) elements.set(id, new FakeElement(id));
    return elements.get(id);
  }

  const payloads = [];
  const fetch = async (url, options = {}) => {
    if (url === '/api/status') {
      return { ok: true, json: async () => ({ model: 'mock-model', key_configured: true }) };
    }
    assert.equal(url, '/api/chat');
    assert.equal(options.method, 'POST');
    const bytes = Buffer.byteLength(options.body, 'utf8');
    assert.ok(bytes <= 40_000, 'browser request must fit server byte cap');
    const payload = JSON.parse(options.body);
    payloads.push({ payload, bytes });
    return { ok: true, json: async () => ({ reply: 'ok' }) };
  };

  const context = vm.createContext({
    document: { getElementById: el, createElement: () => new FakeElement() },
    fetch,
    TextEncoder,
  });
  vm.runInContext(script, context);
  el('token').value = 'local-test-access-token';

  return {
    payloads,
    el,
    async send(message) {
      el('message').value = message;
      await el('form').listeners.submit({ preventDefault() {} });
      assert.equal(el('error').textContent, '', 'request should succeed');
    },
  };
}

test('8000-character message survives as replayed history on follow-up', async () => {
  const h = harness();
  const longMessage = 'a'.repeat(8_000);
  await h.send(longMessage);
  await h.send('continue');
  assert.equal(h.payloads.length, 2);
  assert.equal(h.payloads[1].payload.history[0].content, longMessage);
});

test('Arabic history is byte-bounded and oldest turns are removed', async () => {
  const h = harness();
  for (let i = 0; i < 8; i++) {
    await h.send('ع'.repeat(4_000) + String(i));
  }
  assert.equal(h.payloads.length, 8);
  assert.ok(h.payloads.every(p => p.bytes <= 39_000));
  assert.ok(h.payloads[7].payload.history.length < 8, 'older turns must be evicted');
  assert.equal(h.payloads[7].payload.history.length % 2, 0, 'eviction preserves message pairs');
});

test('New chat clears the history and visible messages', async () => {
  const h = harness();
  await h.send('first');
  h.el('reset').listeners.click();
  await h.send('second');
  assert.equal(h.payloads[1].payload.history.length, 0);
  assert.equal(h.el('messages').children.length, 3);
});
