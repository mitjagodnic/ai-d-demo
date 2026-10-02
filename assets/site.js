/* Zavod AI-D — interaktivnost strani (brez knjižnic) */
(() => {
  "use strict";

  const doc = document.documentElement;
  doc.classList.add("js");
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ROOT = doc.dataset.root || "";
  const CFG = window.AID_CONFIG || {};
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };
  // Slovenian plural forms: 1, 2, 3–4, 5+ (and 101, 102 …)
  const plural = (n, one, two, few, many) => { const m = n % 100; return m === 1 ? one : m === 2 ? two : m === 3 || m === 4 ? few : many; };
  const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

  requestAnimationFrame(() => requestAnimationFrame(() => doc.classList.add("is-loaded")));

  /* ------------------------------------------------------------ toast */
  const toastEl = $("[data-toast]");
  let toastT;
  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("is-on");
    clearTimeout(toastT);
    toastT = setTimeout(() => toastEl.classList.remove("is-on"), 2600);
  }

  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; }
    catch (e) {
      const ta = Object.assign(document.createElement("textarea"), { value: text });
      ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      const ok = document.execCommand("copy"); ta.remove(); return ok;
    }
  }

  /* ------------------------------------------------------------ theme */
  $$("[data-theme-toggle]").forEach((btn) => btn.addEventListener("click", () => {
    const current = doc.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    const apply = () => { doc.dataset.theme = next; store.set("aid-theme", next); };
    if (document.startViewTransition && !reduced) document.startViewTransition(apply); else apply();
  }));

  /* ------------------------------------------------------------ keyboard hint */
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  $$("[data-kbd]").forEach((k) => { k.textContent = isMac ? "⌘K" : "Ctrl K"; });

  /* ------------------------------------------------------------ announcement */
  const ann = $("[data-announce]");
  if (ann) {
    if (store.get("aid-announce") === "hidden") ann.classList.add("is-hidden");
    $("[data-announce-close]", ann)?.addEventListener("click", () => { ann.classList.add("is-hidden"); store.set("aid-announce", "hidden"); });
  }

  /* ------------------------------------------------------------ header */
  const hdr = $("[data-hdr]");
  let lastY = scrollY;
  const onScroll = () => {
    const y = scrollY;
    if (hdr) {
      hdr.classList.toggle("is-scrolled", y > 8);
      const menuOpen = document.body.classList.contains("menu-open");
      hdr.classList.toggle("is-hidden", !menuOpen && y > 400 && y > lastY + 2);
      if (y < lastY - 2) hdr.classList.remove("is-hidden");
    }
    lastY = y;
  };
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ------------------------------------------------------------ mobile menu */
  const menu = $("[data-menu]");
  const burger = $("[data-menu-toggle]");
  function setMenu(open) {
    if (!menu || !burger) return;
    burger.setAttribute("aria-expanded", String(open));
    burger.setAttribute("aria-label", open ? "Zapri meni" : "Odpri meni");
    document.body.classList.toggle("menu-open", open);
    if (open) {
      menu.hidden = false;
      requestAnimationFrame(() => menu.classList.add("is-open"));
      $("a", menu)?.focus({ preventScroll: true });
    } else {
      menu.classList.remove("is-open");
      setTimeout(() => { if (!menu.classList.contains("is-open")) menu.hidden = true; }, 400);
    }
  }
  burger?.addEventListener("click", () => setMenu(burger.getAttribute("aria-expanded") !== "true"));
  menu?.addEventListener("click", (e) => { if (e.target.closest("a")) setMenu(false); });
  addEventListener("keydown", (e) => { if (e.key === "Escape" && document.body.classList.contains("menu-open")) { setMenu(false); burger.focus(); } });
  matchMedia("(min-width: 961px)").addEventListener("change", (m) => { if (m.matches) setMenu(false); });

  /* ------------------------------------------------------------ reveal */
  const revealEls = $$("[data-reveal]");
  if ("IntersectionObserver" in window && !reduced) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        const el = en.target;
        const sibs = el.parentElement ? Array.from(el.parentElement.children).filter((c) => c.hasAttribute("data-reveal")) : [];
        const i = Math.max(0, sibs.indexOf(el));
        el.style.setProperty("--d", `${Math.min(i % 6, 5) * 0.07}s`);
        el.classList.add("is-in");
        io.unobserve(el);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    // reveal what is already on screen right away, the rest as it scrolls into view
    let k = 0;
    revealEls.forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.top < innerHeight && r.bottom > 0) { el.style.setProperty("--d", `${Math.min(k++, 8) * 0.06}s`); el.classList.add("is-in"); }
      else io.observe(el);
    });
  } else {
    revealEls.forEach((el) => el.classList.add("is-in"));
  }

  /* ------------------------------------------------------------ spotlight & magnetic */
  $$("[data-spotlight]").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    });
  });
  if (!reduced && matchMedia("(pointer: fine)").matches) {
    $$("[data-magnetic]").forEach((el) => {
      el.addEventListener("pointermove", (e) => {
        const r = el.getBoundingClientRect();
        const x = e.clientX - r.left, y = e.clientY - r.top;
        el.style.setProperty("--bx", `${x}px`);
        el.style.setProperty("--by", `${y}px`);
        el.style.transform = `translate(${(x - r.width / 2) * 0.12}px, ${(y - r.height / 2) * 0.2}px)`;
      });
      el.addEventListener("pointerleave", () => { el.style.transform = ""; });
    });
  }

  /* ------------------------------------------------------------ hero network */
  $$("[data-network]").forEach((canvas) => {
    const ctx = canvas.getContext("2d");
    const host = canvas.parentElement;
    let W = 0, H = 0, dpr = 1, nodes = [], raf = 0, visible = true;
    const pointer = { x: -9999, y: -9999, active: false };

    function size() {
      const r = host.getBoundingClientRect();
      dpr = Math.min(devicePixelRatio || 1, 2);
      W = r.width; H = r.height;
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.round(Math.min(150, Math.max(46, (W * H) / 11000)));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.22, vy: (Math.random() - 0.5) * 0.22,
        r: Math.random() * 1.4 + 0.5, p: Math.random() * Math.PI * 2, hub: Math.random() < 0.08,
      }));
    }

    function frame(t) {
      ctx.clearRect(0, 0, W, H);
      const maxD = Math.min(150, Math.max(90, W / 11));
      for (const n of nodes) {
        if (!reduced) {
          n.x += n.vx; n.y += n.vy;
          if (pointer.active) {
            const dx = pointer.x - n.x, dy = pointer.y - n.y, d = Math.hypot(dx, dy);
            if (d < 220 && d > 1) { n.x += (dx / d) * 0.35; n.y += (dy / d) * 0.35; }
          }
          if (n.x < -20) n.x = W + 20; if (n.x > W + 20) n.x = -20;
          if (n.y < -20) n.y = H + 20; if (n.y > H + 20) n.y = -20;
        }
      }
      ctx.lineWidth = 0.6;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          if (Math.abs(dx) > maxD || Math.abs(dy) > maxD) continue;
          const d = Math.hypot(dx, dy);
          if (d < maxD) {
            let al = (1 - d / maxD) * 0.28;
            if (pointer.active) {
              const pd = Math.hypot(pointer.x - (a.x + b.x) / 2, pointer.y - (a.y + b.y) / 2);
              if (pd < 200) al += (1 - pd / 200) * 0.5;
            }
            ctx.strokeStyle = `rgba(255,140,70,${al})`;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }
      for (const n of nodes) {
        const pulse = reduced ? 1 : 0.6 + 0.4 * Math.sin(t / 900 + n.p);
        const r = n.hub ? n.r * 2.2 : n.r;
        if (n.hub) {
          const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 9);
          g.addColorStop(0, `rgba(255,170,100,${0.5 * pulse})`); g.addColorStop(1, "rgba(255,107,26,0)");
          ctx.fillStyle = g; ctx.beginPath(); ctx.arc(n.x, n.y, r * 9, 0, Math.PI * 2); ctx.fill();
        }
        ctx.fillStyle = `rgba(255,${n.hub ? 200 : 160},${n.hub ? 140 : 90},${0.55 + 0.45 * pulse})`;
        ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI * 2); ctx.fill();
      }
      if (pointer.active) {
        for (const n of nodes) {
          const d = Math.hypot(pointer.x - n.x, pointer.y - n.y);
          if (d < 160) {
            ctx.strokeStyle = `rgba(255,190,130,${(1 - d / 160) * 0.7})`;
            ctx.beginPath(); ctx.moveTo(pointer.x, pointer.y); ctx.lineTo(n.x, n.y); ctx.stroke();
          }
        }
      }
      if (!reduced && visible) raf = requestAnimationFrame(frame);
    }

    size();
    addEventListener("resize", () => { size(); if (reduced) frame(0); });
    host.addEventListener("pointermove", (e) => {
      const r = canvas.getBoundingClientRect();
      pointer.x = e.clientX - r.left; pointer.y = e.clientY - r.top; pointer.active = true;
    });
    host.addEventListener("pointerleave", () => { pointer.active = false; });
    new IntersectionObserver(([en]) => {
      visible = en.isIntersecting;
      cancelAnimationFrame(raf);
      if (visible) raf = requestAnimationFrame(frame);
    }).observe(canvas);
    raf = requestAnimationFrame(frame);
  });

  /* ------------------------------------------------------------ scroll-highlighted text */
  $$("[data-scrolltext]").forEach((el) => {
    const words = el.textContent.trim().split(/\s+/);
    el.innerHTML = words.map((w) => `<span class="w">${w}</span> `).join("");
    const spans = $$(".w", el);
    if (reduced) { spans.forEach((s) => s.classList.add("on")); return; }
    const update = () => {
      const r = el.getBoundingClientRect();
      const start = innerHeight * 0.85, end = innerHeight * 0.35;
      const p = Math.min(1, Math.max(0, (start - r.top) / (start - end + r.height * 0.6)));
      const n = Math.round(p * spans.length);
      spans.forEach((s, i) => s.classList.toggle("on", i < n));
    };
    addEventListener("scroll", update, { passive: true });
    update();
  });

  /* ------------------------------------------------------------ parallax */
  const par = $$("[data-parallax]");
  if (par.length && !reduced) {
    const upd = () => par.forEach((el) => {
      const r = el.getBoundingClientRect();
      const c = (r.top + r.height / 2 - innerHeight / 2) / innerHeight;
      el.style.setProperty("--py", `${(c * -40).toFixed(1)}px`);
    });
    addEventListener("scroll", upd, { passive: true }); upd();
  }

  /* ------------------------------------------------------------ footer mark glow */
  const mark = $("[data-ftr-mark]");
  mark?.addEventListener("pointermove", (e) => {
    const r = mark.getBoundingClientRect();
    mark.style.setProperty("--mx", `${e.clientX - r.left}px`);
    mark.style.setProperty("--my", `${e.clientY - r.top}px`);
  });

  /* ------------------------------------------------------------ countdowns & event status */
  const cds = $$("[data-countdown]");
  const pad = (n) => String(n).padStart(2, "0");
  function tick() {
    const now = Date.now();
    cds.forEach((el) => {
      const target = Date.parse(el.dataset.countdown);
      let diff = Math.max(0, target - now);
      const d = Math.floor(diff / 864e5); diff -= d * 864e5;
      const h = Math.floor(diff / 36e5); diff -= h * 36e5;
      const m = Math.floor(diff / 6e4); diff -= m * 6e4;
      const s = Math.floor(diff / 1e3);
      const fmt = el.dataset.countdownFormat;
      if (fmt === "full") {
        const set = (k, v) => { const n = el.querySelector(`[data-cd="${k}"]`); if (n && n.textContent !== v) n.textContent = v; };
        set("d", pad(d)); set("h", pad(h)); set("m", pad(m)); set("s", pad(s));
        el.classList.toggle("is-done", target <= now);
      } else if (fmt === "short") {
        el.textContent = target > now ? `še ${d} d ${pad(h)} h ${pad(m)} min` : "";
      } else if (fmt === "days") {
        el.textContent = target > now ? (d > 0 ? `še ${d} ${plural(d, "dan", "dneva", "dnevi", "dni")}` : "danes") : "";
      }
    });
  }
  if (cds.length) { tick(); setInterval(tick, 1000); }
  $$("[data-event-end]").forEach((el) => {
    if (Date.parse(el.dataset.eventEnd) < Date.now()) {
      el.classList.add("is-past");
      $$("[data-status]", el).forEach((s) => { s.textContent = "Zaključen"; s.classList.remove("pill--live"); });
    }
  });

  /* ------------------------------------------------------------ dialogs (speakers) */
  $$("[data-dialog-open]").forEach((btn) => btn.addEventListener("click", () => {
    const dlg = document.getElementById(btn.dataset.dialogOpen);
    if (!dlg) return;
    dlg.showModal();
    dlg.addEventListener("close", () => btn.focus(), { once: true });
  }));
  $$("dialog.speaker").forEach((dlg) => {
    dlg.addEventListener("click", (e) => { if (e.target === dlg || e.target.closest("[data-dialog-close]")) dlg.close(); });
  });

  /* ------------------------------------------------------------ program tabs */
  $$("[data-tabs]").forEach((list) => {
    const tabs = $$("[role=tab]", list);
    const select = (tab, focus) => {
      tabs.forEach((t) => {
        const on = t === tab;
        t.classList.toggle("is-active", on);
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        const panel = document.getElementById(t.getAttribute("aria-controls"));
        if (panel) { panel.hidden = !on; panel.classList.toggle("is-active", on); }
        if (on) $$("[data-reveal]", panel).forEach((el) => el.classList.add("is-in"));
      });
      if (focus) tab.focus();
    };
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => select(t));
      t.addEventListener("keydown", (e) => {
        const k = e.key;
        if (k === "ArrowRight" || k === "ArrowDown") { e.preventDefault(); select(tabs[(i + 1) % tabs.length], true); }
        if (k === "ArrowLeft" || k === "ArrowUp") { e.preventDefault(); select(tabs[(i - 1 + tabs.length) % tabs.length], true); }
        if (k === "Home") { e.preventDefault(); select(tabs[0], true); }
        if (k === "End") { e.preventDefault(); select(tabs[tabs.length - 1], true); }
      });
    });
  });

  /* ------------------------------------------------------------ click-to-load maps */
  function mapSrc(q) { return `https://maps.google.com/maps?q=${encodeURIComponent(q)}&t=m&z=15&output=embed&hl=sl`; }
  function loadMap(box, q) {
    let f = $("iframe", box);
    if (!f) {
      f = document.createElement("iframe");
      f.loading = "lazy"; f.referrerPolicy = "no-referrer-when-downgrade"; f.title = "Zemljevid: " + q;
      box.appendChild(f);
      $("[data-map-load]", box)?.remove();
    }
    f.src = mapSrc(q);
  }
  $$("[data-map]").forEach((box) => $("[data-map-load]", box)?.addEventListener("click", () => loadMap(box, box.dataset.mapQ)));
  $$(".locations").forEach((wrap) => {
    const box = $("[data-map]", wrap);
    $$(".loc", wrap).forEach((b) => b.addEventListener("click", () => {
      $$(".loc", wrap).forEach((x) => x.classList.toggle("is-active", x === b));
      box.dataset.mapQ = b.dataset.mapQ;
      loadMap(box, b.dataset.mapQ);
    }));
  });

  /* ------------------------------------------------------------ copy buttons */
  $$("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
    if (await copyText(b.dataset.copy)) {
      b.classList.add("is-done"); toast("Kopirano: " + b.dataset.copy);
      setTimeout(() => b.classList.remove("is-done"), 1600);
    }
  }));

  /* ------------------------------------------------------------ share */
  const share = $("[data-share]");
  if (share) {
    const url = location.href.split("#")[0];
    const title = share.dataset.title;
    if (navigator.share) doc.classList.add("can-share");
    const links = {
      linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
      x: `https://x.com/intent/post?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`,
      mail: `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(url)}`,
    };
    $$("[data-share-to]", share).forEach((a) => {
      a.href = links[a.dataset.shareTo];
      if (a.dataset.shareTo !== "mail") { a.target = "_blank"; a.rel = "noopener"; }
    });
    $("[data-share-native]", share)?.addEventListener("click", () => navigator.share({ title, url }).catch(() => {}));
    $("[data-copy-link]", share)?.addEventListener("click", async () => { if (await copyText(url)) toast("Povezava je kopirana"); });
  }

  /* ------------------------------------------------------------ reading progress */
  const bar = $("[data-progress]");
  const article = $("[data-article]");
  if (bar && article) {
    const upd = () => {
      const r = article.getBoundingClientRect();
      const p = Math.min(1, Math.max(0, -r.top / (r.height - innerHeight)));
      bar.style.setProperty("--p", p.toFixed(4));
    };
    addEventListener("scroll", upd, { passive: true }); upd();
  }

  /* ------------------------------------------------------------ lightbox */
  const proseImgs = $$("[data-prose] img");
  if (proseImgs.length) {
    const lb = document.createElement("dialog");
    lb.className = "lightbox";
    lb.setAttribute("aria-label", "Povečana slika");
    lb.innerHTML = '<img alt=""><button class="lightbox__close" type="button" aria-label="Zapri"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>';
    document.body.appendChild(lb);
    const big = $("img", lb);
    lb.addEventListener("click", () => lb.close());
    proseImgs.forEach((img) => {
      if (img.closest("a")) return;
      img.addEventListener("click", () => {
        big.src = img.currentSrc || img.src;
        const full = img.getAttribute("srcset")?.split(",").pop().trim().split(" ")[0];
        if (full) big.src = full;
        big.alt = img.alt;
        lb.showModal();
      });
    });
  }

  /* ------------------------------------------------------------ table of contents scrollspy */
  $$("[data-toc]").forEach((toc) => {
    const links = $$("a[href^='#']", toc);
    const map = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) {
          links.forEach((a) => a.classList.remove("is-active"));
          map.get(en.target.id)?.classList.add("is-active");
        }
      });
    }, { rootMargin: "-30% 0px -60% 0px" });
    map.forEach((_, id) => { const s = document.getElementById(id); if (s) io.observe(s); });
  });

  /* ------------------------------------------------------------ back to top */
  $$("[data-top]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" }); }));

  /* ------------------------------------------------------------ membership tiers */
  const tiers = $("[data-tiers]");
  if (tiers) {
    const sel = $("[data-tier-select]");
    const label = $("[data-tier-label]");
    const pick = (btn, scroll) => {
      $$("[data-tier]", tiers).forEach((b) => { const on = b === btn; b.classList.toggle("is-selected", on); b.setAttribute("aria-pressed", String(on)); });
      if (sel) sel.value = btn.dataset.tierName;
      if (label) label.textContent = btn.dataset.tierName;
      if (scroll) document.getElementById("povprasevanje")?.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
    };
    $$("[data-tier]", tiers).forEach((b) => {
      b.addEventListener("click", () => pick(b, false));
      b.addEventListener("dblclick", () => pick(b, true));
    });
    sel?.addEventListener("change", () => { const b = $$("[data-tier]", tiers).find((x) => x.dataset.tierName === sel.value); if (b) pick(b, false); });
    // count-up of prices
    if (!reduced) {
      const io = new IntersectionObserver((entries) => entries.forEach((en) => {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        const el = en.target, to = +el.dataset.count, t0 = performance.now();
        const step = (t) => {
          const k = Math.min(1, (t - t0) / 1400), v = Math.round(to * (1 - Math.pow(1 - k, 4)));
          el.textContent = v.toLocaleString("sl-SI");
          if (k < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }), { threshold: 0.6 });
      $$("[data-count]", tiers).forEach((el) => io.observe(el));
    }
  }

  /* ------------------------------------------------------------ member price toggle */
  $$("[data-member]").forEach((box) => {
    const input = $("[data-member-input]", box), price = $("[data-price]", box);
    input?.addEventListener("change", () => { price.textContent = input.checked ? price.dataset.priceMember : price.dataset.priceFull; });
  });

  /* ------------------------------------------------------------ forms */
  const emailOk = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);
  $$("form[data-form]").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if ($("input[name=website]", form)?.value) return; // bot
      let firstBad = null;
      $$("input, textarea, select", form).forEach((f) => {
        if (f.type === "hidden" || f.classList.contains("hp")) return;
        const wrap = f.closest(".field, .check") || f;
        let bad = false;
        if (f.required && (f.type === "checkbox" ? !f.checked : !f.value.trim())) bad = true;
        if (f.type === "email" && f.value && !emailOk(f.value.trim())) bad = true;
        wrap.classList.toggle("is-invalid", bad);
        f.classList.toggle("is-invalid", bad);
        f.setAttribute("aria-invalid", String(bad));
        if (bad && !firstBad) firstBad = f;
      });
      if (firstBad) { firstBad.focus(); toast(firstBad.type === "email" && firstBad.value ? "Preverite e-naslov." : "Izpolnite obvezna polja."); return; }

      const data = {};
      new FormData(form).forEach((v, k) => { if (k !== "website") data[k] = v; });
      data._subject = form.dataset.subject || "Sporočilo s spletne strani";
      data._stran = location.href;
      const done = () => {
        const ok = $("[data-form-done]", form);
        if (ok) ok.hidden = false; else toast("Hvala! Prijava je oddana.");
        form.reset();
      };
      if (CFG.formEndpoint) {
        form.classList.add("is-sending");
        try {
          const res = await fetch(CFG.formEndpoint, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(data) });
          if (!res.ok) throw new Error(res.status);
          done();
        } catch (err) {
          toast("Pošiljanje ni uspelo. Pišite nam na " + (CFG.email || "info@ai-d.si"));
        } finally { form.classList.remove("is-sending"); }
      } else {
        const labels = {};
        $$("label[for]", form).forEach((l) => { const f = document.getElementById(l.htmlFor); if (f) labels[f.name] = l.textContent.replace("*", "").trim(); });
        const body = Object.entries(data).filter(([k]) => !k.startsWith("_")).map(([k, v]) => `${labels[k] || k}: ${v}`).join("\n");
        location.href = `mailto:${CFG.email || "info@ai-d.si"}?subject=${encodeURIComponent(data._subject)}&body=${encodeURIComponent(body + "\n\n" + data._stran)}`;
        done();
      }
    });
    form.addEventListener("input", (e) => {
      const f = e.target; const wrap = f.closest(".field, .check") || f;
      if (wrap.classList.contains("is-invalid")) { wrap.classList.remove("is-invalid"); f.classList.remove("is-invalid"); f.removeAttribute("aria-invalid"); }
    });
  });

  /* ------------------------------------------------------------ news filtering */
  const grid = $("[data-news-grid]");
  if (grid) {
    const cards = $$("[data-card]", grid);
    const q = $("[data-news-q]");
    const count = $("[data-news-count]");
    const more = $("[data-news-more]");
    const empty = $("[data-news-empty]");
    const tools = $("[data-news-tools]");
    const PAGE = 12;
    const state = { q: "", topic: "", year: "", limit: PAGE };
    const params = new URLSearchParams(location.search);
    state.q = params.get("q") || ""; state.topic = params.get("tema") || ""; state.year = params.get("leto") || "";
    if (q) q.value = state.q;
    cards.forEach((c) => { c._s = norm(c.dataset.search); });

    const setChips = (attr, val) => $$(`[${attr}]`).forEach((b) => b.classList.toggle("is-active", b.getAttribute(attr) === val));
    function render(resetLimit) {
      if (resetLimit) state.limit = PAGE;
      const terms = norm(state.q).split(/\s+/).filter(Boolean);
      let shown = 0, matched = 0;
      cards.forEach((c) => {
        const ok = (!state.topic || c.dataset.topic === state.topic) && (!state.year || c.dataset.year === state.year) && terms.every((t) => c._s.includes(t));
        if (ok) matched++;
        const vis = ok && shown < state.limit;
        if (vis) shown++;
        c.classList.toggle("is-hidden", !vis);
        if (vis) c.classList.add("is-in");
      });
      count.textContent = matched === cards.length ? `Prikazanih ${shown} od ${cards.length} objav` : `${matched} ${plural(matched, "zadetek", "zadetka", "zadetki", "zadetkov")}`;
      more.parentElement.hidden = shown >= matched;
      empty.hidden = matched > 0;
      setChips("data-topic-chip", state.topic); setChips("data-year-chip", state.year);
      const p = new URLSearchParams();
      if (state.q) p.set("q", state.q); if (state.topic) p.set("tema", state.topic); if (state.year) p.set("leto", state.year);
      history.replaceState(null, "", p.toString() ? `?${p}` : location.pathname);
    }
    let bodies = null;
    const loadBodies = () => bodies || (bodies = fetch(ROOT + "assets/search.json").then((r) => r.json()).then((idx) => {
      const byUrl = new Map(idx.map((it) => [it.u, it.b || ""]));
      cards.forEach((c) => {
        const href = decodeURIComponent($("a", c).getAttribute("href")).replace(/^(\.\.\/)+/, "");
        c._s += " " + norm(byUrl.get(href) || "");
      });
    }).catch(() => {}));
    let qt;
    q?.addEventListener("focus", loadBodies, { once: true });
    q?.addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(async () => { state.q = q.value; await loadBodies(); render(true); }, 120); });
    $$("[data-topic-chip]").forEach((b) => b.addEventListener("click", () => { state.topic = b.dataset.topicChip; render(true); }));
    $$("[data-year-chip]").forEach((b) => b.addEventListener("click", () => { state.year = b.dataset.yearChip; render(true); }));
    more?.addEventListener("click", () => { state.limit += PAGE; render(false); });
    $("[data-news-reset]")?.addEventListener("click", () => { state.q = state.topic = state.year = ""; if (q) q.value = ""; render(true); });
    $$("[data-view]").forEach((b) => b.addEventListener("click", () => {
      const list = b.dataset.view === "list";
      grid.classList.toggle("is-list", list);
      $$("[data-view]").forEach((x) => { x.classList.toggle("is-active", x === b); x.setAttribute("aria-pressed", String(x === b)); });
      store.set("aid-news-view", b.dataset.view);
    }));
    if (store.get("aid-news-view") === "list") $("[data-view=list]")?.click();
    if (tools) {
      const sentinel = document.createElement("div");
      tools.before(sentinel);
      new IntersectionObserver(([en]) => tools.classList.toggle("is-stuck", !en.isIntersecting)).observe(sentinel);
    }
    render(true);
    if (state.q) loadBodies().then(() => render(true));
  }

  /* ------------------------------------------------------------ command palette */
  const cmdk = $("[data-cmdk]");
  if (cmdk) {
    const input = $("[data-cmdk-input]", cmdk);
    const results = $("[data-cmdk-results]", cmdk);
    const countEl = $("[data-cmdk-count]", cmdk);
    let index = null, items = [], active = 0;
    const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

    async function loadIndex() {
      if (index) return index;
      try {
        const res = await fetch(ROOT + "assets/search.json");
        index = (await res.json()).map((it) => ({ ...it, _t: norm(it.t), _x: norm(it.x), _b: norm(it.b) }));
      } catch (e) { index = []; }
      return index;
    }
    function highlight(text, terms) {
      let out = esc(text);
      terms.forEach((t) => {
        if (t.length < 2) return;
        const n = norm(text); const i = n.indexOf(t);
        if (i >= 0) {
          const orig = text.substr(i, t.length);
          out = out.replace(esc(orig), `<mark>${esc(orig)}</mark>`);
        }
      });
      return out;
    }
    function search(qs) {
      const terms = norm(qs).split(/\s+/).filter(Boolean);
      if (!terms.length) {
        const pages = index.filter((i) => i.k === "Stran");
        const news = index.filter((i) => i.k === "Novica").slice(0, 5);
        const events = index.filter((i) => i.k === "Dogodek").slice(0, 3);
        return { groups: [["Strani", pages], ["Dogodki", events], ["Zadnje novice", news]], total: index.length, terms };
      }
      const scored = [];
      for (const it of index) {
        let s = 0, ok = true;
        for (const t of terms) {
          const inT = it._t.indexOf(t), inX = it._x.indexOf(t), inB = it._b.indexOf(t);
          if (inT < 0 && inX < 0 && inB < 0) { ok = false; break; }
          s += inT === 0 ? 12 : inT > 0 ? 8 : 0;
          s += inX >= 0 ? 3 : 0;
          s += inB >= 0 ? 1 : 0;
        }
        if (ok) scored.push([s + (it.k === "Stran" ? 2 : 0), it]);
      }
      scored.sort((a, b) => b[0] - a[0]);
      return { groups: [["Zadetki", scored.slice(0, 30).map((x) => x[1])]], total: scored.length, terms };
    }
    function render() {
      const { groups, total, terms } = search(input.value);
      items = [];
      let html = "";
      groups.forEach(([name, list]) => {
        if (!list.length) return;
        html += `<div class="cmdk__group">${esc(name)}</div>`;
        list.forEach((it) => {
          const i = items.length; items.push(it);
          html += `<a class="cmdk__item" role="option" id="cmdk-${i}" aria-selected="${i === 0}" href="${esc(ROOT + encodeURI(it.u))}">
            <span class="cmdk__t">${highlight(it.t, terms)}</span><span class="cmdk__k">${esc(it.k)}${it.d ? "<br>" + esc(it.d) : ""}</span>
            <span class="cmdk__x">${esc(it.x || "")}</span></a>`;
        });
      });
      results.innerHTML = html || `<p class="cmdk__empty">Ni zadetkov za »${esc(input.value)}«.</p>`;
      countEl.textContent = input.value ? `${total} ${plural(total, "zadetek", "zadetka", "zadetki", "zadetkov")}` : "";
      active = 0;
    }
    function move(d) {
      if (!items.length) return;
      active = (active + d + items.length) % items.length;
      $$(".cmdk__item", results).forEach((el, i) => el.setAttribute("aria-selected", String(i === active)));
      $(`#cmdk-${active}`, results)?.scrollIntoView({ block: "nearest" });
    }
    async function open(prefill) {
      if (cmdk.open) return;
      setMenu(false);
      cmdk.showModal();
      input.value = prefill || "";
      results.innerHTML = '<p class="cmdk__empty">Nalagam …</p>';
      await loadIndex();
      render();
      input.focus();
    }
    $$("[data-search-open]").forEach((b) => b.addEventListener("click", () => open()));
    addEventListener("keydown", (e) => {
      const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); cmdk.open ? cmdk.close() : open(); }
      else if (e.key === "/" && !typing && !cmdk.open) { e.preventDefault(); open(); }
    });
    let it;
    input.addEventListener("input", () => { clearTimeout(it); it = setTimeout(render, 60); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Enter") { e.preventDefault(); const a = $(`#cmdk-${active}`, results); if (a) location.href = a.href; }
    });
    results.addEventListener("pointermove", (e) => {
      const a = e.target.closest(".cmdk__item"); if (!a) return;
      const i = +a.id.split("-")[1]; if (i !== active) { active = i; $$(".cmdk__item", results).forEach((el, j) => el.setAttribute("aria-selected", String(j === active))); }
    });
    cmdk.addEventListener("click", (e) => { if (e.target === cmdk) cmdk.close(); });
  }
})();
