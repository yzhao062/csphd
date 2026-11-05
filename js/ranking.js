(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Ranking = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Weights are whole tenths and location carries one decimal, so a weighted sum in
  // hundredths stays an exact integer and two tied schools cannot split on rounding.
  var PRESETS = {
    research: { csrankings: 5, usnews: 3, location: 2 },
    balanced: { csrankings: 4, usnews: 4, location: 2 },
  };

  // Returns new rows, best first, each with `combined` and a competition `rank` (1, 2, 2, 4).
  function rankSchools(schools, preset) {
    var rows = schools.map(function (s) {
      var row = {};
      for (var key in s) row[key] = s[key];
      row.hundredths = 10 * preset.csrankings * s.csrankings + 10 * preset.usnews * s.usnews
        + preset.location * Math.round(s.location * 10);
      return row;
    });
    rows.sort(function (a, b) {
      return a.hundredths - b.hundredths || a.csrankings - b.csrankings
        || (a.school < b.school ? -1 : 1);
    });
    var rank = 0;
    rows.forEach(function (row, i) {
      if (i === 0 || row.hundredths !== rows[i - 1].hundredths) rank = i + 1;
      row.rank = rank;
      row.combined = row.hundredths / 100;
    });
    return rows;
  }

  return { PRESETS: PRESETS, rankSchools: rankSchools };
});
