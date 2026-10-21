// Camera rolls (horizontal snap) and section tracking for the vertical snap page.
(function () {
  const snap = document.getElementById("snap");
  const panels = Array.from(document.querySelectorAll(".panel"));
  const railLinks = Array.from(document.querySelectorAll(".rail a"));
  const where = document.querySelector(".topbar .where");
  let current = panels[0];

  // Rolls
  document.querySelectorAll("[data-roll]").forEach(roll => {
    const track = roll.querySelector(".roll-track");
    const shots = Array.from(track.children);
    const dots = Array.from(roll.querySelectorAll(".dots i"));
    const count = roll.querySelector(".count");
    const prev = roll.querySelector(".prev");
    const next = roll.querySelector(".next");

    const index = () => {
      const left = track.scrollLeft;
      let best = 0, d = Infinity;
      shots.forEach((s, i) => {
        const dd = Math.abs(s.offsetLeft - track.offsetLeft - left);
        if (dd < d) { d = dd; best = i; }
      });
      if (track.scrollLeft + track.clientWidth >= track.scrollWidth - 4) best = shots.length - 1;
      return best;
    };
    const pos = s => s.offsetLeft - track.offsetLeft;
    const go = i => {
      i = Math.max(0, Math.min(shots.length - 1, i));
      track.scrollTo({ left: pos(shots[i]), behavior: "smooth" });
    };
    // At the end of the track several shots share the max scroll offset, so
    // index() - 1 may not move at all. Skip to the nearest shot that does, and
    // step from the pending target while a smooth scroll is still running.
    let target = null, targetAt = 0;
    const step = d => {
      const max = track.scrollWidth - track.clientWidth;
      const at = k => Math.min(pos(shots[k]), max);
      const base = target !== null && Date.now() - targetAt < 700 ? target : index();
      let i = base + d;
      while (i > 0 && i < shots.length - 1 && Math.abs(at(i) - at(base)) <= 4) i += d;
      if (i < 0 || i >= shots.length || Math.abs(at(i) - at(base)) <= 4) return;
      target = i; targetAt = Date.now();
      go(i);
    };
    const update = () => {
      target = null;
      const i = index();
      dots.forEach((d, k) => d.classList.toggle("on", k === i));
      count.textContent = (i + 1) + " / " + shots.length;
      prev.disabled = i === 0;
      next.disabled = i === shots.length - 1;
      shots.forEach((s, k) => {
        const v = s.querySelector("video");
        if (v && k !== i && !v.paused) v.pause();
      });
    };
    let t;
    track.addEventListener("scroll", () => { clearTimeout(t); t = setTimeout(update, 60); }, { passive: true });
    prev.addEventListener("click", () => step(-1));
    next.addEventListener("click", () => step(1));
    track.addEventListener("keydown", e => {
      if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
    });
    roll._go = step;
    update();
  });

  // Global left/right moves the roll of the section in view
  document.addEventListener("keydown", e => {
    if (e.target.closest && e.target.closest(".roll-track, input, textarea, select, video")) return;
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const roll = current && current.querySelector("[data-roll]");
    if (!roll) return;
    e.preventDefault();
    roll._go(e.key === "ArrowRight" ? 1 : -1);
  });

  // Track the section in view
  const io = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (!en.isIntersecting) return;
      current = en.target;
      const id = "#" + en.target.id;
      railLinks.forEach(a => a.classList.toggle("on", a.getAttribute("href") === id));
      if (where) where.textContent = en.target.id === "top" ? "" : en.target.dataset.title || "";
      if (history.replaceState) history.replaceState(null, "", id === "#top" ? location.pathname : id);
    });
  }, { root: snap, threshold: 0.55 });
  panels.forEach(p => io.observe(p));

  // Anchor links scroll inside the snap container
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener("click", e => {
      const el = document.querySelector(a.getAttribute("href"));
      if (!el) return;
      e.preventDefault();
      snap.scrollTo({ top: el.offsetTop, behavior: "smooth" });
    });
  });
  if (location.hash) {
    const el = document.querySelector(location.hash);
    if (el) snap.scrollTop = el.offsetTop;
  }
})();
