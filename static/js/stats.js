(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const labels = { again: "rating.again", hard: "rating.hard", good: "rating.good", easy: "rating.easy" };
  const formatSeconds = (seconds) => SA.t("stats.seconds", { seconds: Number(seconds || 0).toFixed(1) });

  async function load() {
    try {
      const data = await SA.api("/api/study/stats");
      $("stats-total").textContent = data.total;
      $("stats-reviewed").textContent = data.reviewed;
      $("stats-average-duration").textContent = formatSeconds(data.average_duration);
      const max = Math.max(1, ...Object.values(data.ratings).map((rating) => rating.count));
      const bars = $("rating-bars");
      bars.replaceChildren();
      Object.keys(labels).forEach((rating) => {
        const row = document.createElement("div");
        row.className = "stats-bar-row";
        const label = document.createElement("span");
        label.textContent = SA.t(labels[rating]);
        const track = document.createElement("span");
        track.className = "stats-bar-track";
        const fill = document.createElement("span");
        const summary = data.ratings[rating] || { count: 0, average_duration: 0 };
        fill.style.width = (summary.count / max * 100) + "%";
        track.append(fill);
        const count = document.createElement("strong");
        count.textContent = summary.count + " · " + formatSeconds(summary.average_duration);
        row.append(label, track, count);
        bars.append(row);
      });
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }
  SA.ready.then(load);
})();
