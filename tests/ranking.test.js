const test = require("node:test");
const assert = require("node:assert");
const { PRESETS, rankSchools } = require("../js/ranking.js");

function school(name, csrankings, usnews, location) {
  return { school: name, csrankings, usnews, location };
}

function names(rows) {
  return rows.map((r) => r.school);
}

test("every preset's weights add up to ten tenths", () => {
  for (const preset of Object.values(PRESETS)) {
    assert.strictEqual(preset.csrankings + preset.usnews + preset.location, 10);
  }
});

test("the combined score is the weighted average of the three signals", () => {
  const rows = rankSchools([school("UW", 6, 49, 14.9)], PRESETS.research);
  assert.strictEqual(rows[0].combined, 20.68);
});

test("the research preset favours CSRankings more than the balanced one", () => {
  const research = school("Research U", 5, 45, 20);
  const brand = school("Brand U", 40, 4, 20);
  assert.deepStrictEqual(names(rankSchools([brand, research], PRESETS.research)),
    ["Research U", "Brand U"]);
  assert.deepStrictEqual(names(rankSchools([research, brand], PRESETS.balanced)),
    ["Brand U", "Research U"]);
});

test("a better location lifts a school with equal ranks", () => {
  const rows = rankSchools([school("Town", 10, 10, 60), school("City", 10, 10, 5)], PRESETS.research);
  assert.deepStrictEqual(names(rows), ["City", "Town"]);
});

test("equal scores tie even where floating point would split them", () => {
  const rows = rankSchools([
    school("A", 3, 1, 0.1),
    school("B", 1, 1, 5.1),
    school("C", 9, 9, 9.9),
  ], PRESETS.research);
  assert.deepStrictEqual(rows.map((r) => r.rank), [1, 1, 3]);
});

test("rows keep their other fields and input rows are left unchanged", () => {
  const input = [{ school: "A", city: "X, PA", csrankings: 1, usnews: 2, location: 3 }];
  const rows = rankSchools(input, PRESETS.balanced);
  assert.strictEqual(rows[0].city, "X, PA");
  assert.deepStrictEqual(input, [{ school: "A", city: "X, PA", csrankings: 1, usnews: 2, location: 3 }]);
});
