(function () {
  var nav = document.querySelector(".nav");
  var btn = document.querySelector(".nav-btn");
  var menu = document.querySelector(".menu");

  if (btn) {
    btn.addEventListener("click", function (e) {
      if (!nav.classList.contains("open")) {
        e.preventDefault();
        nav.classList.add("open");
      }
    });
  }
  document.querySelectorAll("[data-open-menu]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      menu.classList.add("open");
    });
  });
  var close = document.querySelector(".close-menu");
  if (close) {
    close.addEventListener("click", function () {
      menu.classList.remove("open");
      nav.classList.remove("open");
    });
  }

  // "5 years ago" style relative dates, refreshed on load
  var units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  document.querySelectorAll("[data-ts]").forEach(function (el) {
    var secs = Math.floor(Date.now() / 1000) - Number(el.dataset.ts);
    var text = "just now";
    for (var i = 0; i < units.length; i++) {
      var n = Math.floor(secs / units[i][1]);
      if (n >= 1) { text = n + " " + units[i][0] + (n > 1 ? "s" : "") + " ago"; break; }
    }
    el.textContent = text;
  });

  // client-side search over the built index
  var form = document.querySelector(".search-bar form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = form.q.value.trim();
      if (q) location.href = form.dataset.root + "search.html?q=" + encodeURIComponent(q);
    });
  }
})();
