// PREMEYFILES - basic JavaScript
// 1) mobile menu  2) live search suggestions  3) fade-in on scroll

(function () {
  // ---- 1. Mobile menu
  var toggle = document.getElementById("navToggle");
  var links = document.getElementById("navLinks");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      toggle.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // ---- 2. Live search suggestions
  var input = document.getElementById("liveSearch");
  var box = document.getElementById("suggestBox");
  var timer = null;

  function hideBox() {
    if (box) { box.hidden = true; box.innerHTML = ""; }
  }

  if (input && box) {
    input.addEventListener("input", function () {
      clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < 2) { hideBox(); return; }
      timer = setTimeout(function () {
        fetch("/api/public/search?q=" + encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (items) {
            box.innerHTML = "";
            if (!items.length) { hideBox(); return; }
            items.forEach(function (item) {
              var a = document.createElement("a");
              a.href = item.url;
              var title = document.createElement("span");
              title.textContent = item.title;          // textContent = safe, no HTML injection
              var cat = document.createElement("small");
              cat.textContent = item.category;
              a.appendChild(title);
              a.appendChild(cat);
              box.appendChild(a);
            });
            box.hidden = false;
          })
          .catch(hideBox);
      }, 250);
    });
    document.addEventListener("click", function (e) {
      if (!box.contains(e.target) && e.target !== input) hideBox();
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") hideBox();
    });
  }

  // ---- 3. Fade-in on scroll
  var items = document.querySelectorAll(".card, .cat-card, .stat, .about-box");
  if ("IntersectionObserver" in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    items.forEach(function (el) { el.classList.add("reveal"); observer.observe(el); });
  }
})();
