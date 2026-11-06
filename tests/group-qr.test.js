const test = require('node:test');
const assert = require('node:assert/strict');
const { validate, expired, imageUrl } = require('../js/group-qr.js');
const group = { name: '测试群', image: 'assets/groups/jobs.jpg', expiresAt: '2026-11-12T00:00:00+08:00' };

test('expiry uses the configured timezone and is exclusive at the boundary', () => {
  assert.equal(expired(group, Date.parse('2026-11-11T15:59:59Z')), false);
  assert.equal(expired(group, Date.parse('2026-11-11T16:00:00Z')), true);
  assert.equal(expired(group, Date.parse('2026-11-12T00:00:00Z')), true);
});
test('each group expires independently', () => {
  const later = { ...group, expiresAt: '2026-11-19T00:00:00+08:00' };
  const now = Date.parse('2026-11-13T00:00:00Z');
  assert.equal(expired(group, now), true);
  assert.equal(expired(later, now), false);
});
test('reject missing dates, ambiguous timezones, invalid dates and nonlocal images', () => {
  for (const expiresAt of ['', '2026-11-12', '2026-11-12T00:00:00', 'invalid']) {
    assert.throws(() => validate([{ ...group, expiresAt }]));
  }
  assert.throws(() => validate([{ ...group, image: 'https://example.com/qr.jpg' }]));
  assert.throws(() => validate([]));
  assert.deepEqual(validate([group]), [group]);
});
test('refreshing expiration changes image cache version without changing path', () => {
  const refreshed = { ...group, expiresAt: '2026-11-19T00:00:00+08:00' };
  assert.notEqual(imageUrl(group), imageUrl(refreshed));
  assert.equal(imageUrl(group).split('?')[0], imageUrl(refreshed).split('?')[0]);
  assert.notEqual(imageUrl(group), imageUrl({ ...group, version: '2' }));
});

test('page hides contact before expiry and replaces QR with required remark at expiry', async () => {
  const vm = require('node:vm');
  const fs = require('node:fs');
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren() { this.children = []; }
    addEventListener() {}
    text() { return this.textContent + this.children.map(child => child.text()).join(' '); }
    images() { return (this.tag === 'img' ? 1 : 0) + this.children.reduce((n, child) => n + child.images(), 0); }
  }
  const container = new Element('div');
  const status = new Element('p');
  let now = Date.parse(group.expiresAt) - 1;
  let tick;
  class Clock extends Date { static now() { return now; } }
  await vm.runInNewContext(fs.readFileSync(require.resolve('../js/join.js'), 'utf8'), {
    document: {
      getElementById: id => id === 'groups' ? container : status,
      createElement: tag => new Element(tag), addEventListener() {}
    },
    fetch: async () => ({ ok: true, json: async () => [group] }),
    GroupQR: { validate, expired, imageUrl }, Date: Clock, Intl,
    setInterval: callback => { tick = callback; }
  });
  assert.equal(container.images(), 1);
  assert.equal(container.text().includes('yzhao062'), false);
  now += 1;
  tick();
  assert.equal(container.images(), 0);
  assert.match(container.text(), /yzhao062/);
  assert.match(container.text(), /必须备注「学校\/单位 \+ 姓名」/);
});

test('CI returns failure for an expired QR', () => {
  const vm = require('node:vm');
  const fs = require('node:fs');
  const path = require('node:path');
  const result = {};
  vm.runInNewContext(fs.readFileSync(require.resolve('../tools/check_group_qr.js'), 'utf8'), {
    require: name => name === 'node:fs' ? {
      readFileSync: () => JSON.stringify([{ ...group, expiresAt: '2000-01-01T00:00:00Z' }]),
      existsSync: () => true
    } : name === 'node:path' ? path : { validate, expired },
    __dirname, process: result, console: { log() {}, error() {} }
  });
  assert.equal(result.exitCode, 1);
});
