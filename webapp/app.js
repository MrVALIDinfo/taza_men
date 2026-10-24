(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  const inTelegram = Boolean(tg && tg.initData);
  const params = new URLSearchParams(location.search);
  const MODE = params.get("mode") === "pick" ? "pick" : "app";
  const BISHKEK = [42.8746, 74.5698];

  // ---------- тексты ----------
  const I18N = {
    ru: {
      tagline: "Карта экологических нарушений",
      loading: "Загружаем карту нарушений…",
      stat_total: "обращений", stat_pending: "на модерации", stat_approved: "подтверждено",
      all: "Все", report: "Сообщить",
      report_hint: "Отправьте фото нарушения в чат с ботом — AI проверит его, а затем вы укажете место.",
      pick_hint: "Передвиньте карту, чтобы метка указала на место нарушения",
      pick_send: "Отправить эту точку",
      tab_map: "Карта", tab_my: "Мои", tab_rating: "Рейтинг", tab_moderation: "Модерация",
      my_title: "Мои обращения",
      my_empty: "Вы ещё не отправляли обращений. Сфотографируйте нарушение и отправьте боту!",
      rating_title: "Лучшие эко-активисты",
      rating_empty: "Пока никто не получил баллы — станьте первым!",
      reward_title: "Вознаграждение за нарушения",
      reward_text: "За каждое нарушение, подтверждённое инспектором, — +{points} баллов.",
      moderation_title: "Очередь модерации",
      moderation_empty: "Очередь пуста — все обращения рассмотрены ✨",
      demo_banner: "Демо-режим: модерация открыта всем, чтобы можно было проверить весь сценарий.",
      need_tg: "Откройте Taza Map в Telegram, чтобы увидеть этот раздел.",
      points: "баллов", approved: "подтверждено", pending: "на модерации",
      level_next: "До уровня «{level}»: {left} баллов", level_max: "Максимальный уровень 🎉",
      on_map: "На карте", address_only: "место указано адресом",
      approve: "Подтвердить", reject: "Отклонить",
      confirm_approve: "Подтвердить нарушение? Житель получит +{points} баллов.",
      reject_title: "Причина отклонения", reject_msg: "Житель получит уведомление с причиной.",
      reason_no_violation: "Нет нарушения", reason_bad_photo: "Плохое фото", reason_duplicate: "Дубликат",
      approved_toast: "Подтверждено — житель получил баллы 🏆", rejected_toast: "Обращение отклонено",
      already: "Обращение уже рассмотрено", error: "Ошибка загрузки. Попробуйте ещё раз.",
      locate_error: "Не удалось определить местоположение",
      ai_violation: "AI: нарушение", ai_review: "AI: нужна проверка",
      confidence: "уверенность", burning: "Горит!", reporter: "Отправил",
    },
    ky: {
      tagline: "Экологиялык бузуулар картасы",
      loading: "Бузуулар картасы жүктөлүүдө…",
      stat_total: "арыз", stat_pending: "модерацияда", stat_approved: "ырасталды",
      all: "Баары", report: "Билдирүү",
      report_hint: "Бузуунун сүрөтүн бот менен чатка жибериңиз — AI аны текшерет, андан кийин жерин көрсөтөсүз.",
      pick_hint: "Белги бузуу болгон жерди көрсөтүшү үчүн картаны жылдырыңыз",
      pick_send: "Ушул чекитти жөнөтүү",
      tab_map: "Карта", tab_my: "Меники", tab_rating: "Рейтинг", tab_moderation: "Модерация",
      my_title: "Менин арыздарым",
      my_empty: "Сиз азырынча арыз жөнөтө элексиз. Бузууну сүрөткө тартып, ботко жибериңиз!",
      rating_title: "Мыкты эко-активисттер",
      rating_empty: "Азырынча эч ким упай ала элек — биринчи болуңуз!",
      reward_title: "Бузуулар үчүн сыйлык",
      reward_text: "Инспектор ырастаган ар бир бузуу үчүн — +{points} упай.",
      moderation_title: "Модерация кезеги",
      moderation_empty: "Кезек бош — бардык арыздар каралды ✨",
      demo_banner: "Демо-режим: бүт сценарийди текшерүү үчүн модерация баарына ачык.",
      need_tg: "Бул бөлүмдү көрүү үчүн Taza Map'ти Telegram'да ачыңыз.",
      points: "упай", approved: "ырасталды", pending: "модерацияда",
      level_next: "«{level}» деңгээлине чейин: {left} упай", level_max: "Эң жогорку деңгээл 🎉",
      on_map: "Картада", address_only: "жери дарек менен көрсөтүлгөн",
      approve: "Ырастоо", reject: "Четке кагуу",
      confirm_approve: "Бузууну ырастайсызбы? Жашоочу +{points} упай алат.",
      reject_title: "Четке кагуунун себеби", reject_msg: "Жашоочуга себеби менен билдирүү барат.",
      reason_no_violation: "Бузуу жок", reason_bad_photo: "Сүрөт начар", reason_duplicate: "Кайталанган",
      approved_toast: "Ырасталды — жашоочу упай алды 🏆", rejected_toast: "Арыз четке кагылды",
      already: "Арыз мурунтан каралган", error: "Жүктөөдө ката. Кайра аракет кылыңыз.",
      locate_error: "Жайгашкан жерди аныктоо мүмкүн болгон жок",
      ai_violation: "AI: бузуу", ai_review: "AI: текшерүү керек",
      confidence: "ишенимдүүлүк", burning: "Күйүп жатат!", reporter: "Жөнөткөн",
    },
  };

  const VIOLATIONS = {
    illegal_dump: { emoji: "🗑", ru: "Стихийная свалка", ky: "Мыйзамсыз таштанды үймөгү" },
    waste_burning: { emoji: "🔥", ru: "Сжигание мусора", ky: "Таштанды өрттөө" },
    water_pollution: { emoji: "💧", ru: "Загрязнение воды", ky: "Сууну булгоо" },
    hazardous_waste: { emoji: "☣️", ru: "Опасные отходы", ky: "Коркунучтуу калдыктар" },
    overflowing_bin: { emoji: "🚮", ru: "Переполненный контейнер", ky: "Толуп кеткен контейнер" },
    none: { emoji: "❔", ru: "Нарушение", ky: "Бузуу" },
  };
  const WASTE = {
    household: { ru: "бытовой", ky: "тиричилик" },
    construction: { ru: "строительный", ky: "курулуш" },
    hazardous: { ru: "опасный", ky: "коркунучтуу" },
    mixed: { ru: "смешанный", ky: "аралаш" },
  };
  const STATUS = {
    pending: { ru: "🕓 На модерации", ky: "🕓 Модерацияда" },
    approved: { ru: "✅ Подтверждено", ky: "✅ Ырасталды" },
    rejected: { ru: "❌ Отклонено", ky: "❌ Четке кагылды" },
  };
  const LEVELS = [
    { min: 0, ru: "Новичок", ky: "Жаңы баштоочу" },
    { min: 300, ru: "Активист", ky: "Активист" },
    { min: 1000, ru: "Эко-герой", ky: "Эко-баатыр" },
    { min: 3000, ru: "Хранитель города", ky: "Шаардын коргоочусу" },
  ];

  let lang = params.get("lang");
  if (!I18N[lang]) {
    const code = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code) || "";
    lang = code.startsWith("ky") ? "ky" : "ru";
  }

  const state = { points: [], filter: "all", me: null, rewardPoints: 100, view: "map", moderation: [] };
  const markersById = new Map();

  // ---------- утилиты ----------
  const $ = (id) => document.getElementById(id);
  const tr = (key, vars = {}) =>
    (I18N[lang][key] || I18N.ru[key] || key).replace(/\{(\w+)\}/g, (_, k) => (k in vars ? vars[k] : ""));
  const name = (dict, key) => (dict[key] || dict.none || {})[lang] || "";
  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const fmtDate = (iso) => {
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const fmtVolume = (v) => (v >= 1 ? Math.round(v) : Math.round(v * 10) / 10 || "<0.1");

  function haptic(kind) {
    if (!tg || !tg.HapticFeedback) return;
    if (kind === "select") tg.HapticFeedback.selectionChanged();
    else tg.HapticFeedback.notificationOccurred(kind);
  }

  let toastTimer;
  function toast(msg) {
    const el = $("toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (el.hidden = true), 2600);
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", "X-Telegram-Init-Data": (tg && tg.initData) || "", ...(options.headers || {}) },
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(body.error || res.statusText);
      err.status = res.status;
      throw err;
    }
    return body;
  }

  // ---------- карта ----------
  const isDark = (tg && tg.colorScheme ? tg.colorScheme : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") === "dark";
  const map = L.map("map", { zoomControl: false, attributionControl: true }).setView(BISHKEK, 12);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);
  // тёмная тема Telegram — инвертируем подложку, маркеры остаются цветными
  if (isDark) $("map").classList.add("dark-tiles");

  const cluster = L.markerClusterGroup({
    showCoverageOnHover: false,
    maxClusterRadius: 48,
    iconCreateFunction: (c) =>
      L.divIcon({ html: `<div class="marker-cluster-custom">${c.getChildCount()}</div>`, className: "", iconSize: [42, 42] }),
  });
  map.addLayer(cluster);

  function popupHtml(p) {
    return `
      <div class="popup-title">${VIOLATIONS[p.violation_type || "none"].emoji} ${esc(name(VIOLATIONS, p.violation_type || "none"))}</div>
      <span class="badge ${p.status}">${esc(name(STATUS, p.status))}</span>
      ${p.burning ? `<div class="popup-meta">🔥 ${tr("burning")}</div>` : ""}
      <div class="popup-meta">📦 ~${fmtVolume(p.volume_m3 || 0)} м³ · №${p.id}</div>
      <div class="popup-meta">🕓 ${fmtDate(p.created_at)}</div>`;
  }

  function renderMarkers() {
    cluster.clearLayers();
    markersById.clear();
    const visible = state.points.filter((p) => state.filter === "all" || p.violation_type === state.filter);
    for (const p of visible) {
      const v = VIOLATIONS[p.violation_type] || VIOLATIONS.none;
      const icon = L.divIcon({
        html: `<div class="marker ${p.status}${p.burning ? " burning" : ""}">${v.emoji}</div>`,
        className: "",
        iconSize: [34, 34],
        iconAnchor: [17, 17],
        popupAnchor: [0, -16],
      });
      const marker = L.marker([p.lat, p.lon], { icon }).bindPopup(popupHtml(p));
      markersById.set(p.id, marker);
      cluster.addLayer(marker);
    }
  }

  function renderChips() {
    const keys = ["all", ...Object.keys(VIOLATIONS).filter((k) => k !== "none")];
    $("filterChips").innerHTML = keys
      .map((k) => {
        const label = k === "all" ? tr("all") : `${VIOLATIONS[k].emoji} ${name(VIOLATIONS, k)}`;
        return `<button class="chip${state.filter === k ? " active" : ""}" data-filter="${k}">${esc(label)}</button>`;
      })
      .join("");
  }

  $("filterChips").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-filter]");
    if (!chip) return;
    state.filter = chip.dataset.filter;
    haptic("select");
    renderChips();
    renderMarkers();
  });

  async function loadMap() {
    try {
      const data = await api("/api/map");
      state.points = data.points;
      $("statTotal").textContent = data.stats.total;
      $("statPending").textContent = data.stats.pending;
      $("statApproved").textContent = data.stats.approved;
      renderMarkers();
    } catch (e) {
      toast(tr("error"));
    }
  }

  function showOnMap(id, lat, lon) {
    switchView("map");
    setTimeout(() => {
      map.flyTo([lat, lon], 17, { duration: 0.8 });
      const marker = markersById.get(id);
      if (marker) map.once("moveend", () => cluster.zoomToShowLayer(marker, () => marker.openPopup()));
    }, 60);
  }

  let meMarker;
  function locate(silent) {
    if (!navigator.geolocation) return !silent && toast(tr("locate_error"));
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const ll = [pos.coords.latitude, pos.coords.longitude];
        map.flyTo(ll, 16, { duration: 0.8 });
        if (MODE !== "pick") {
          if (meMarker) meMarker.setLatLng(ll);
          else meMarker = L.circleMarker(ll, { radius: 8, color: "#fff", weight: 3, fillColor: "#3B82F6", fillOpacity: 1 }).addTo(map);
        }
      },
      () => !silent && toast(tr("locate_error")),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }
  $("locateBtn").addEventListener("click", () => {
    haptic("select");
    locate(false);
  });

  $("reportBtn").addEventListener("click", () => {
    haptic("select");
    if (tg && inTelegram) tg.showAlert(tr("report_hint"), () => tg.close());
    else alert(tr("report_hint"));
  });

  // ---------- вкладки ----------
  function switchView(view) {
    state.view = view;
    document.querySelectorAll(".view").forEach((el) => el.classList.toggle("active", el.id === `view-${view}`));
    document.querySelectorAll(".tab").forEach((el) => el.classList.toggle("active", el.dataset.view === view));
    if (view === "map") setTimeout(() => map.invalidateSize(), 0);
    if (view === "my") loadMe();
    if (view === "rating") loadRating();
    if (view === "moderation") loadModeration();
  }
  $("tabbar").addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab || tab.dataset.view === state.view) return;
    haptic("select");
    switchView(tab.dataset.view);
  });

  const needTelegram = () => `<div class="need-tg">📱<br>${esc(tr("need_tg"))}</div>`;
  const empty = (emoji, text) => `<div class="empty"><span class="empty-emoji">${emoji}</span>${esc(text)}</div>`;

  // ---------- мои обращения ----------
  function levelInfo(points) {
    let current = LEVELS[0];
    let next = null;
    for (const level of LEVELS) {
      if (points >= level.min) current = level;
      else if (!next) next = level;
    }
    return { current, next };
  }

  function renderMe() {
    const me = state.me;
    if (!me) return;
    const u = me.user;
    const { current, next } = levelInfo(u.points);
    const pending = me.complaints.filter((c) => c.status === "pending").length;
    const progress = next ? Math.round(((u.points - current.min) / (next.min - current.min)) * 100) : 100;
    $("profileCard").innerHTML = `
      <div class="profile-head">
        <div class="avatar">${esc((u.first_name || "?").slice(0, 1).toUpperCase())}</div>
        <div><div class="profile-name">${esc(u.first_name || "")}</div><div class="profile-level">🌿 ${esc(current[lang])}</div></div>
      </div>
      <div class="profile-stats">
        <div><b>${u.points}</b><span>🏆 ${tr("points")}</span></div>
        <div><b>${u.approved}</b><span>${tr("approved")}</span></div>
        <div><b>${pending}</b><span>${tr("pending")}</span></div>
      </div>
      <div class="progress"><i style="width:${progress}%"></i></div>
      <div class="progress-label">${next ? esc(tr("level_next", { level: next[lang], left: next.min - u.points })) : tr("level_max")}</div>`;

    $("myList").innerHTML = me.complaints.length
      ? me.complaints
          .map((c) => {
            const place = c.address ? esc(c.address) : c.lat != null ? `${c.lat.toFixed(4)}, ${c.lon.toFixed(4)}` : "";
            return `
            <div class="item card" ${c.lat != null ? `data-show="${c.id}" data-lat="${c.lat}" data-lon="${c.lon}"` : ""}>
              <img class="thumb" src="${c.photo_url}" loading="lazy" alt="">
              <div class="item-body">
                <div class="item-title">${VIOLATIONS[c.violation_type || "none"].emoji} ${esc(name(VIOLATIONS, c.violation_type || "none"))}</div>
                <div class="item-sub">№${c.id} · ${fmtDate(c.created_at)}</div>
                <div class="item-sub">📍 ${place}</div>
                <span class="badge ${c.status}">${esc(name(STATUS, c.status))}</span>
              </div>
            </div>`;
          })
          .join("")
      : empty("📸", tr("my_empty"));
  }

  $("myList").addEventListener("click", (e) => {
    const item = e.target.closest("[data-show]");
    if (!item) return;
    haptic("select");
    showOnMap(Number(item.dataset.show), Number(item.dataset.lat), Number(item.dataset.lon));
  });

  async function loadMe() {
    if (!inTelegram) {
      $("profileCard").hidden = true;
      $("myList").innerHTML = needTelegram();
      return;
    }
    try {
      state.me = await api("/api/me");
      state.rewardPoints = state.me.reward_points;
      if (!params.get("lang") && state.me.user.lang !== lang) {
        lang = state.me.user.lang;
        applyI18n();
      }
      $("moderationTab").hidden = !state.me.user.is_admin;
      $("demoBanner").hidden = !state.me.user.demo_mode;
      renderMe();
    } catch (e) {
      $("myList").innerHTML = empty("⚠️", tr("error"));
    }
  }

  // ---------- рейтинг ----------
  async function loadRating() {
    $("rewardText").textContent = tr("reward_text", { points: state.rewardPoints });
    try {
      const { leaders } = await api("/api/leaderboard");
      const medals = ["🥇", "🥈", "🥉"];
      $("ratingList").innerHTML = leaders.length
        ? leaders
            .map(
              (l) => `
            <div class="leader card${l.is_me ? " me" : ""}">
              <div class="rank">${medals[l.rank - 1] || l.rank}</div>
              <div class="leader-name">${esc(l.name)}</div>
              <div class="leader-points">${l.points}<span>${l.approved} · ${tr("approved")}</span></div>
            </div>`
            )
            .join("")
        : empty("🌱", tr("rating_empty"));
    } catch (e) {
      $("ratingList").innerHTML = empty("⚠️", tr("error"));
    }
  }

  // ---------- модерация ----------
  function aiReason(item) {
    try {
      const ai = JSON.parse(item.ai_json || "{}");
      return ai[`reason_${lang}`] || ai.reason_ru || "";
    } catch (e) {
      return "";
    }
  }

  function renderModeration() {
    const items = state.moderation;
    $("queueCount").textContent = items.length;
    $("moderationDot").hidden = items.length === 0;
    $("moderationList").innerHTML = items.length
      ? items
          .map((m) => {
            const v = VIOLATIONS[m.violation_type || "none"];
            const chips = [
              m.waste_type && WASTE[m.waste_type] ? `<span class="ai-chip">🗑 ${esc(WASTE[m.waste_type][lang])}</span>` : "",
              `<span class="ai-chip">📦 ~${fmtVolume(m.volume_m3 || 0)} м³</span>`,
              m.burning ? `<span class="ai-chip hot">🔥 ${tr("burning")}</span>` : "",
              `<span class="ai-chip">🎯 ${Math.round((m.confidence || 0) * 100)}% ${tr("confidence")}</span>`,
              `<span class="ai-chip">${m.verdict === "accept" ? tr("ai_violation") : tr("ai_review")}</span>`,
            ].join("");
            const place =
              m.lat != null
                ? `📍 ${m.lat.toFixed(5)}, ${m.lon.toFixed(5)} · <button data-show="${m.id}" data-lat="${m.lat}" data-lon="${m.lon}">${tr("on_map")}</button>`
                : `📍 ${esc(m.address || "")} <span class="item-sub">(${tr("address_only")})</span>`;
            return `
            <div class="mod card" id="mod-${m.id}">
              <img class="mod-photo" src="${m.photo_url}" data-zoom loading="lazy" alt="">
              <div class="mod-body">
                <div class="mod-head">
                  <div class="mod-title">${v.emoji} ${esc(name(VIOLATIONS, m.violation_type || "none"))}</div>
                  <div class="mod-id">№${m.id}</div>
                </div>
                <div class="ai-chips">${chips}</div>
                <div class="ai-reason">🤖 ${esc(aiReason(m))}</div>
                <div class="mod-place">${place}</div>
                <div class="item-sub">👤 ${tr("reporter")}: ${esc(m.reporter)} · ${fmtDate(m.created_at)}</div>
                <div class="mod-actions">
                  <button class="btn btn-reject" data-reject="${m.id}">✕ ${tr("reject")}</button>
                  <button class="btn btn-approve" data-approve="${m.id}">✓ ${tr("approve")}</button>
                </div>
              </div>
            </div>`;
          })
          .join("")
      : empty("✨", tr("moderation_empty"));
  }

  async function loadModeration() {
    if (!inTelegram) {
      $("moderationList").innerHTML = needTelegram();
      return;
    }
    try {
      state.moderation = (await api("/api/moderation")).items;
      renderModeration();
    } catch (e) {
      $("moderationList").innerHTML = empty("⚠️", tr("error"));
    }
  }

  async function moderate(id, action, comment) {
    const card = $(`mod-${id}`);
    card && card.querySelectorAll("button.btn").forEach((b) => (b.disabled = true));
    try {
      await api(`/api/moderation/${id}`, { method: "POST", body: JSON.stringify({ action, comment }) });
      haptic(action === "approve" ? "success" : "warning");
      toast(action === "approve" ? tr("approved_toast") : tr("rejected_toast"));
      if (card) card.classList.add("leaving");
      setTimeout(() => {
        state.moderation = state.moderation.filter((m) => m.id !== id);
        renderModeration();
      }, 300);
      loadMap();
    } catch (e) {
      haptic("error");
      toast(e.status === 409 ? tr("already") : tr("error"));
      card && card.querySelectorAll("button.btn").forEach((b) => (b.disabled = false));
      if (e.status === 409) loadModeration();
    }
  }

  $("moderationList").addEventListener("click", (e) => {
    const approve = e.target.closest("[data-approve]");
    const reject = e.target.closest("[data-reject]");
    const show = e.target.closest("[data-show]");
    const zoom = e.target.closest("[data-zoom]");
    if (approve) {
      const id = Number(approve.dataset.approve);
      const text = tr("confirm_approve", { points: state.rewardPoints });
      if (tg && inTelegram) tg.showConfirm(text, (ok) => ok && moderate(id, "approve"));
      else if (confirm(text)) moderate(id, "approve");
    } else if (reject) {
      const id = Number(reject.dataset.reject);
      const reasons = ["no_violation", "bad_photo", "duplicate"];
      if (tg && inTelegram && tg.isVersionAtLeast("6.2")) {
        tg.showPopup(
          {
            title: tr("reject_title"),
            message: tr("reject_msg"),
            buttons: reasons.map((r) => ({ id: r, type: r === "duplicate" ? "destructive" : "default", text: tr(`reason_${r}`) })),
          },
          (buttonId) => buttonId && moderate(id, "reject", tr(`reason_${buttonId}`))
        );
      } else {
        moderate(id, "reject", tr("reason_no_violation"));
      }
    } else if (show) {
      showOnMap(Number(show.dataset.show), Number(show.dataset.lat), Number(show.dataset.lon));
    } else if (zoom) {
      openLightbox(zoom.src);
    }
  });

  // ---------- просмотр фото ----------
  function closeLightbox() {
    $("lightbox").hidden = true;
    if (tg && tg.BackButton) {
      tg.BackButton.hide();
      tg.BackButton.offClick(closeLightbox);
    }
  }
  function openLightbox(src) {
    $("lightboxImg").src = src;
    $("lightbox").hidden = false;
    if (tg && tg.BackButton && inTelegram) {
      tg.BackButton.show();
      tg.BackButton.onClick(closeLightbox);
    }
  }
  $("lightbox").addEventListener("click", closeLightbox);

  // ---------- язык ----------
  function applyI18n() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = tr(el.dataset.i18n)));
    document.querySelectorAll("#langSwitch button").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
    $("rewardText").textContent = tr("reward_text", { points: state.rewardPoints });
    renderChips();
    renderMarkers();
    renderMe();
    if (state.moderation.length || state.view === "moderation") renderModeration();
  }
  $("langSwitch").addEventListener("click", (e) => {
    const b = e.target.closest("[data-lang]");
    if (!b || b.dataset.lang === lang) return;
    lang = b.dataset.lang;
    haptic("select");
    applyI18n();
    if (state.view === "rating") loadRating();
  });

  // ---------- режим выбора точки (кнопка «Указать на карте» в боте) ----------
  function initPick() {
    document.body.classList.add("pick-mode");
    $("pickOverlay").hidden = false;
    setTimeout(() => map.invalidateSize(), 0);
    const updateCoords = () => {
      const c = map.getCenter();
      $("pickCoords").textContent = `${c.lat.toFixed(5)}, ${c.lng.toFixed(5)}`;
    };
    map.on("move", updateCoords);
    updateCoords();
    locate(true);
    if (tg && inTelegram) {
      tg.MainButton.setParams({ text: tr("pick_send"), color: "#1DBF73", text_color: "#ffffff", is_visible: true });
      tg.MainButton.onClick(() => {
        const c = map.getCenter();
        haptic("success");
        tg.sendData(JSON.stringify({ lat: c.lat, lon: c.lng }));
      });
    }
  }

  // ---------- экран загрузки ----------
  const splashShownAt = Date.now();
  let splashHidden = false;
  function hideSplash() {
    if (splashHidden) return;
    splashHidden = true;
    // показываем хотя бы 600 мс, чтобы экран не «мигал» на быстром интернете
    setTimeout(() => {
      $("splash").classList.add("done");
      setTimeout(() => $("splash").remove(), 400);
    }, Math.max(0, 600 - (Date.now() - splashShownAt)));
  }

  // ---------- старт ----------
  $("splashText").textContent = tr("loading");
  if (tg) {
    tg.ready();
    tg.expand();
    if (inTelegram) {
      document.documentElement.dataset.tg = "1";
      if (tg.isVersionAtLeast("7.7")) tg.disableVerticalSwipes();
      try {
        tg.setHeaderColor("bg_color");
        tg.setBackgroundColor("secondary_bg_color");
      } catch (e) { /* старые клиенты */ }
    }
  }

  applyI18n();
  // убираем заставку, когда пришли данные и отрисовались плитки карты (или через 6 с в любом случае)
  Promise.all([loadMap(), new Promise((resolve) => map.whenReady(() => setTimeout(resolve, 300)))]).then(hideSplash);
  setTimeout(hideSplash, 6000);
  if (MODE === "pick") {
    initPick();
  } else {
    if (inTelegram) loadMe();
    setInterval(() => state.view === "map" && loadMap(), 60000);
  }
})();
