const test = require("node:test");
const assert = require("node:assert");
const { daysBetween, recencyTag } = require("../js/recency.js");

test("daysBetween counts whole days", () => {
  assert.strictEqual(daysBetween("2026-06-01", "2026-06-15"), 14);
});

test("cold start (firstSeen == trackStart) yields no badge", () => {
  assert.strictEqual(recencyTag("2026-06-30", "2026-06-30", "2026-06-30", "2026-06-30", 14), "");
});

test("new within window yields 新", () => {
  assert.strictEqual(recencyTag("2026-07-02", "2026-07-02", "2026-06-30", "2026-07-05", 14), "新");
});

test("updated within window yields 更新", () => {
  assert.strictEqual(recencyTag("2026-06-30", "2026-07-03", "2026-06-30", "2026-07-05", 14), "更新");
});

test("change older than window yields no badge", () => {
  assert.strictEqual(recencyTag("2026-06-30", "2026-07-01", "2026-06-30", "2026-07-20", 14), "");
});

test("new beats updated", () => {
  assert.strictEqual(recencyTag("2026-07-04", "2026-07-04", "2026-06-30", "2026-07-05", 14), "新");
});

test("no tracking data yields no badge", () => {
  assert.strictEqual(recencyTag("", "", "", "2026-07-05", 14), "");
});