// Zoom layer: picture links in a roll open above the page instead of a new tab.
// Without JS the links still open the image itself.
(function () {
  const links = Array.from(document.querySelectorAll("[data-roll] a.m-img"));
  if (!links.length || typeof HTMLDialogElement === "undefined") return;

  const dlg = document.createElement("dialog");
  dlg.className = "zoom";
  dlg.setAttribute("aria-label", "Picture viewer");
  dlg.innerHTML =
    '<div class="zoom-bar">' +
      '<button type="button" class="zoom-back"><span aria-hidden="true">&larr;</span> Back</button>' +
      '<span class="zoom-count" aria-live="polite"></span>' +
    '</div>' +
    '<figure class="zoom-fig">' +
      '<img class="zoom-img" alt="">' +
      '<figcaption class="zoom-cap"></figcaption>' +
    '</figure>' +
    '<button type="button" class="zoom-nav zoom-prev" aria-label="Previous picture">&larr;</button>' +
    '<button type="button" class="zoom-nav zoom-next" aria-label="Next picture">&rarr;</button>';
  document.body.appendChild(dlg);

  const img = dlg.querySelector(".zoom-img");
  const cap = dlg.querySelector(".zoom-cap");
  const count = dlg.querySelector(".zoom-count");
  const prev = dlg.querySelector(".zoom-prev");
  const next = dlg.querySelector(".zoom-next");
  let group = [], at = 0, opener = null;

  const show = i => {
    at = (i + group.length) % group.length;
    const a = group[at];
    const thumb = a.querySelector("img");
    const title = a.closest(".shot")?.querySelector(".shot-h");
    img.src = a.getAttribute("href");
    img.alt = thumb ? thumb.alt : "";
    img.classList.toggle("is-diagram", a.classList.contains("m-diagram"));
    cap.textContent = title ? title.textContent.replace(/^\d+/, "").trim() : "";
    count.textContent = (at + 1) + " / " + group.length;
    prev.hidden = next.hidden = group.length < 2;
  };
  const open = a => {
    group = Array.from(a.closest("[data-roll]").querySelectorAll("a.m-img"));
    opener = a;
    show(group.indexOf(a));
    document.documentElement.classList.add("zoom-open");
    dlg.showModal();
    dlg.querySelector(".zoom-back").focus();
  };
  // Runs on Back/backdrop directly and on the dialog's close event (Esc), whichever comes first.
  const cleanup = () => {
    if (!opener) return;
    document.documentElement.classList.remove("zoom-open");
    img.removeAttribute("src");
    const a = opener;
    opener = null;
    a.focus({ preventScroll: true });
  };
  const close = () => { if (dlg.open) dlg.close(); cleanup(); };

  links.forEach(a => a.addEventListener("click", e => {
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    open(a);
  }));
  dlg.addEventListener("close", cleanup);
  dlg.querySelector(".zoom-back").addEventListener("click", close);
  prev.addEventListener("click", () => show(at - 1));
  next.addEventListener("click", () => show(at + 1));
  // Backdrop click: the dialog itself is the target only outside its content.
  dlg.addEventListener("click", e => { if (e.target === dlg || e.target.classList.contains("zoom-fig")) close(); });
  dlg.addEventListener("keydown", e => {
    if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); show(at + 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); show(at - 1); }
  });

  // Swipe left/right on touch screens
  let x0 = null, y0 = 0;
  dlg.addEventListener("touchstart", e => { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
  dlg.addEventListener("touchend", e => {
    if (x0 === null || group.length < 2) return;
    const dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
    x0 = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) show(at + (dx < 0 ? 1 : -1));
  }, { passive: true });
})();
