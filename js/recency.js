(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Recency = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Whole-day difference (b - a) between two "YYYY-MM-DD" dates; NaN if unparseable.
  function daysBetween(aIso, bIso) {
    var a = Date.parse(aIso + "T00:00:00Z");
    var b = Date.parse(bIso + "T00:00:00Z");
    if (isNaN(a) || isNaN(b)) return NaN;
    return Math.round((b - a) / 86400000);
  }

  // "新" if the row first appeared after tracking began and within the window;
  // "更新" if its content last changed after tracking began and within the window;
  // "" otherwise — including the cold start (firstSeen == trackStart) and dateless data.
  function recencyTag(firstSeen, lastChanged, trackStart, synced, windowDays) {
    if (!trackStart || !synced) return "";
    function fresh(d) {
      if (!d || d <= trackStart) return false;
      var n = daysBetween(d, synced);
      return !isNaN(n) && n >= 0 && n <= windowDays;
    }
    if (fresh(firstSeen)) return "新";
    if (fresh(lastChanged)) return "更新";
    return "";
  }

  return { daysBetween: daysBetween, recencyTag: recencyTag };
});