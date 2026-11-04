// app.js — BookVerse frontend логика: ходит в FastAPI (JSON),
// рисует каталог / корзину / заказ с анимациями.

const API = "/api";
const TOKEN_KEY = "bv_token";

let cart = {}; // { product_id: quantity }
let currentCategory = 0;
let currentProducts = [];
let currentUser = null;

const $ = (sel) => document.querySelector(sel);

// --- Токен / пользователь ---
function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); }

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", "Bearer " + token);
  const res = await fetch(API + path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.error?.message || "Ошибка запроса");
  return data;
}

/* ---------- Авторизация (UI) ---------- */
function openAuth() { $("#auth-modal").style.display = "flex"; switchAuthTab("login"); }
function closeAuth() { $("#auth-modal").style.display = "none"; }
function switchAuthTab(tab) {
  const isLogin = tab === "login";
  $("#tab-login").classList.toggle("active", isLogin);
  $("#tab-register").classList.toggle("active", !isLogin);
  $("#login-form").style.display = isLogin ? "flex" : "none";
  $("#register-form").style.display = isLogin ? "none" : "flex";
}

async function handleLogin(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const data = await apiFetch("/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
    });
    setToken(data.token);
    currentUser = data.user;
    closeAuth();
    renderAuth();
    loadFavorites();
    toast("С возвращением, " + data.user.name + "!");
  } catch (err) { toast(err.message, false); }
}

async function handleRegister(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const data = await apiFetch("/auth/register", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: form.get("name"), email: form.get("email"), password: form.get("password"),
        phone: "", address: "",
      }),
    });
    setToken(data.token);
    currentUser = data.user;
    closeAuth();
    renderAuth();
    loadFavorites();
    toast("Аккаунт создан, добро пожаловать, " + data.user.name + "!");
  } catch (err) { toast(err.message, false); }
}

function logout() {
  setToken(null);
  currentUser = null;
  renderAuth();
  favorites.clear();
  favoriteItems = [];
  updateFavBadge();
  currentProducts.forEach((p) => (p.in_fav = false));
  const listEl = $("#products");
  if (listEl) renderProducts(currentProducts);
  toast("Вы вышли из аккаунта");
}

async function checkAuth() {
  if (!getToken()) { renderAuth(); return; }
  try {
    const user = await apiFetch("/auth/me");
    currentUser = user;
  } catch {
    setToken(null);
    currentUser = null;
    favorites.clear();
    favoriteItems = [];
    updateFavBadge();
  }
  renderAuth();
}

function renderAuth() {
  const area = $("#auth-area");
  if (!area) return;
  refreshAnalyticsGate();
  if (currentUser) {
    area.innerHTML =
      '<div class="auth-user" title="' + escapeAttr(currentUser.email) + '">' +
        '<span class="avatar">' + escapeHtml((currentUser.name || "?").charAt(0).toUpperCase()) + "</span>" +
        '<span class="uname">' + escapeHtml(currentUser.name) + "</span>" +
        '<button class="logout" onclick="logout()" title="Выйти">⎋</button>' +
      "</div>";
  } else {
    area.innerHTML = '<button class="btn btn-ghost" onclick="openAuth()">Войти</button>';
  }
}

$("#login-form").addEventListener("submit", handleLogin);
$("#register-form").addEventListener("submit", handleRegister);

function money(n) {
  return Number(n).toLocaleString("ru-RU") + " ₽";
}

/* ---------- Тосты ---------- */
function toast(text, ok = true) {
  const wrap = $("#toast-wrap");
  const el = document.createElement("div");
  el.className = "toast " + (ok ? "ok" : "err");
  el.textContent = (ok ? "✓ " : "⚠ ") + text;
  wrap.appendChild(el);
  setTimeout(() => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 320);
  }, 3000);
}

/* ---------- Лоадер ---------- */
function setLoading(on) {
  $("#loader").classList.toggle("show", !!on);
}

/* ---------- Данные ---------- */
async function loadProducts() {
  const q = $("#search").value.trim();
  const params = new URLSearchParams();
  if (currentCategory) params.set("category", currentCategory);
  if (q) params.set("q", q);
  params.set("limit", "500");

  try {
    setLoading(true);
    await new Promise((r) => setTimeout(r, 250)); // лёгкая пауза для визуального отклика
    const products = await apiFetch("/products?" + params.toString());
    currentProducts = products;
    renderProducts(products);
  } catch (e) {
    toast(e.message, false);
  } finally {
    setLoading(false);
  }
}

async function loadCategories() {
  try {
    const cats = await apiFetch("/categories");
    const el = $("#categories");
    el.innerHTML =
      '<a href="#" data-cat="0" class="' + (currentCategory === 0 ? "active" : "") + '">Все книги</a>' +
      cats.map((c) =>
        '<a href="#" data-cat="' + c.id + '" class="' + (currentCategory === c.id ? "active" : "") + '">' +
        escapeHtml(c.name) + "</a>"
      ).join("");
    el.querySelectorAll("a").forEach((a) =>
      a.addEventListener("click", (e) => {
        e.preventDefault();
        currentCategory = Number(a.dataset.cat);
        loadProducts();
        el.querySelectorAll("a").forEach((x) => x.classList.remove("active"));
        a.classList.add("active");
      })
    );
    const catEl = $("#stat-cats");
    if (catEl) catEl.textContent = cats.length;
  } catch (e) {
    toast(e.message, false);
  }
}

function renderProducts(products) {
  const el = $("#products");
  if (!products.length) {
    el.innerHTML = '<div class="empty">По вашему запросу ничего не найдено.</div>';
    return;
  }
  el.innerHTML = products.map((p, i) => `
    <div class="product-card" style="animation-delay:${i * 0.06}s">
      <button class="fav-btn ${p.in_fav ? "active" : ""}" onclick="toggleFavorite(${p.id}, '${escapeJs(p.name)}')" title="В избранное">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="${p.in_fav ? "currentColor" : "none"}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>
      </button>
      ${p.category_name ? `<span class="cat-tag">${escapeHtml(p.category_name)}</span>` : ""}
      <h3>${escapeHtml(p.name)}</h3>
      <div class="author">${escapeHtml(p.author || "Автор не указан")}</div>
      <div class="price-row">
        <span class="price">${money(p.base_price)}</span>
      </div>
      <div class="stock ${p.in_stock > 0 ? "in" : "out"}">
        ${p.in_stock > 0 ? "● В наличии — " + p.in_stock + " шт." : "● Нет в наличии"}
      </div>
      <div class="card-actions">
        ${p.in_stock > 0
          ? `<button class="btn btn-buy" onclick="addToCart(${p.id}, '${escapeJs(p.name)}', ${p.base_price})">🛒 В корзину</button>`
          : ""}
        <button class="btn btn-ghost btn-complaint" onclick="openComplaint(${p.id}, '${escapeJs(p.name)}')" title="Сообщить о проблеме">⚠</button>
      </div>
    </div>`).join("");

  // Стаггер + reveal для карточек
  requestAnimationFrame(() => {
    el.querySelectorAll(".product-card").forEach((c) => c.classList.add("show"));
  });

  const statEl = $("#stat-books");
  if (statEl) statEl.textContent = products.length;
  bindDynamicFx();
}

/* ---------- Корзина ---------- */
function addToCart(id, name, price) {
  if (cart[id]) cart[id] += 1; else cart[id] = 1;
  updateCartBadge(true);
  toast("Добавлено: «" + name + "»");
}

function updateCartBadge(pop = false) {
  const count = Object.values(cart).reduce((a, b) => a + b, 0);
  const badge = $("#cart-count");
  if (!badge) return;
  badge.textContent = count;
  if (pop) {
    badge.classList.remove("pop");
    void badge.offsetWidth;
    badge.classList.add("pop");
  }
}

function cartItems() {
  return currentProducts
    .filter((p) => cart[p.id])
    .map((p) => ({ ...p, quantity: cart[p.id], subtotal: p.base_price * cart[p.id] }));
}

function showCart() {
  ["catalog", "checkout"].forEach((id) => ($("#" + id).style.display = "none"));
  $("#cart").style.display = "block";
  $("#cart").classList.remove("slide-panel");
  void $("#cart").offsetWidth;
  $("#cart").classList.add("slide-panel");

  const items = cartItems();
  const list = $("#cart-items");
  list.innerHTML = items.length
    ? items.map((it) => `
      <div class="cart-row">
        <div>
          <div class="c-name">${escapeHtml(it.name)}</div>
          <div class="c-price">${money(it.base_price)}</div>
        </div>
        <input type="number" class="qty-input" value="${it.quantity}" min="1" onchange="setQty(${it.id}, this.value)">
        <div class="c-subtotal">${money(it.subtotal)}</div>
        <button class="btn-dell" onclick="removeItem(${it.id})" title="Удалить">🗑️</button>
      </div>`).join("")
    : '<div class="cart-empty">Корзина пуста — добавьте книги из каталога.</div>';

  const total = items.reduce((a, it) => a + it.subtotal, 0);
  $("#cart-total").textContent = "Итого: " + money(total);
}

function setQty(id, val) {
  cart[id] = Math.max(1, Number(val) || 1);
  showCart();
}

function removeItem(id) {
  delete cart[id];
  updateCartBadge();
  showCart();
}

/* ---------- Избранное ---------- */
let favorites = new Set(); // id книг в избранном
let favoriteItems = []; // полные объекты товаров из /api/favorites

async function loadFavorites() {
  if (!getToken()) {
    favorites.clear();
    updateFavBadge();
    return;
  }
  try {
    const favs = await apiFetch("/favorites");
    favorites = new Set(favs.map((p) => p.id));
    favoriteItems = favs; // полный список избранного из API
    // помечаем карточки в текущем каталоге
    currentProducts.forEach((p) => (p.in_fav = favorites.has(p.id)));
    const listEl = $("#products");
    if (listEl) renderProducts(currentProducts);
    updateFavBadge();
    renderFavoritesPage();
  } catch (e) {
    // молча, чтобы не мешать
  }
}

function updateFavBadge() {
  const badge = $("#fav-count");
  if (badge) badge.textContent = favorites.size;
}

async function toggleFavorite(id, name) {
  if (!getToken()) {
    openAuth();
    toast("Войдите, чтобы добавлять в избранное", false);
    return;
  }
  const isFav = favorites.has(id);
  try {
    if (isFav) {
      await apiFetch("/favorites/" + id, { method: "DELETE" });
      favorites.delete(id);
      favoriteItems = favoriteItems.filter((p) => p.id !== id);
      toast("Убрано из избранного: «" + name + "»");
    } else {
      await apiFetch("/favorites", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: id }),
      });
      favorites.add(id);
      // подтянем полный список избранного (с полными объектами товаров)
      const favs = await apiFetch("/favorites");
      favorites = new Set(favs.map((p) => p.id));
      favoriteItems = favs;
      toast("Добавлено в избранное: «" + name + "»");
    }
    // отмечаем сердечки в каталоге без полной перерисовки карточек
    currentProducts.forEach((p) => p.in_fav = favorites.has(p.id));
    markFavButtons();
    updateFavBadge();
    renderFavoritesPage();
  } catch (e) {
    toast(e.message, false);
  }
}

// Обновляет только класс active у сердечек в каталоге/избранном — без перерисовки
function markFavButtons() {
  document.querySelectorAll(".product-card").forEach((card) => {
    const btn = card.querySelector(".fav-btn");
    if (!btn) return;
    // id книги хранится в onclick как первый аргумент
    const m = (btn.getAttribute("onclick") || "").match(/toggleFavorite\((\d+)/);
    if (!m) return;
    const pid = Number(m[1]);
    btn.classList.toggle("active", favorites.has(pid));
    const svg = btn.querySelector("path");
    if (svg) svg.setAttribute("fill", favorites.has(pid) ? "currentColor" : "none");
  });
}

function renderFavoritesPage() {
  const el = $("#fav-items");
  if (!el) return;
  if (!getToken()) {
    el.innerHTML = '<div class="empty">Войдите, чтобы видеть избранное.</div>';
    return;
  }
  // рендерим из полного списка избранного (favoriteItems), а не из каталога
  const items = favoriteItems.length ? favoriteItems : currentProducts.filter((p) => favorites.has(p.id));
  if (!items.length) {
    el.innerHTML = '<div class="empty">В избранном пока пусто — нажмите ♥ на интересной книге.</div>';
    return;
  }
  el.innerHTML = items.map((p, i) => `
    <div class="product-card" style="animation-delay:${i * 0.05}s">
      <button class="fav-btn active" onclick="toggleFavorite(${p.id}, '${escapeJs(p.name)}')" title="Убрать из избранного">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>
      </button>
      ${p.category_name ? `<span class="cat-tag">${escapeHtml(p.category_name)}</span>` : ""}
      <h3>${escapeHtml(p.name)}</h3>
      <div class="author">${escapeHtml(p.author || "Автор не указан")}</div>
      <div class="price-row"><span class="price">${money(p.base_price)}</span></div>
      <div class="stock ${p.in_stock > 0 ? "in" : "out"}">${p.in_stock > 0 ? "● В наличии — " + p.in_stock + " шт." : "● Нет в наличии"}</div>
      <div class="card-actions">
        ${p.in_stock > 0
          ? `<button class="btn btn-buy" onclick="addToCart(${p.id}, '${escapeJs(p.name)}', ${p.base_price})">🛒 В корзину</button>`
          : ""}
        <button class="btn btn-ghost btn-complaint" onclick="openComplaint(${p.id}, '${escapeJs(p.name)}')" title="Сообщить о проблеме">⚠</button>
      </div>
    </div>`).join("");
}

function showFavorites() {
  ["catalog", "cart", "checkout"].forEach((id) => ($("#" + id).style.display = "none"));
  $("#favorites").style.display = "block";
  $("#favorites").classList.remove("slide-panel");
  void $("#favorites").offsetWidth;
  $("#favorites").classList.add("slide-panel");
  renderFavoritesPage();
}

function showCatalog() {
  ["cart", "checkout", "favorites"].forEach((id) => ($("#" + id).style.display = "none"));
  $("#catalog").style.display = "block";
  document.querySelectorAll(".reveal").forEach((el) => el.classList.add("visible"));
}

/* ---------- Чекаут ---------- */
function showCheckout() {
  const items = cartItems();
  if (!items.length) return toast("Корзина пуста", false);

  ["catalog", "cart"].forEach((id) => ($("#" + id).style.display = "none"));
  $("#checkout").style.display = "block";
  $("#checkout").classList.remove("slide-panel");
  void $("#checkout").offsetWidth;
  $("#checkout").classList.add("slide-panel");

  $("#checkout-summary").innerHTML =
    items.map((it) => `<p>${escapeHtml(it.name)} × ${it.quantity} — ${money(it.subtotal)}</p>`).join("") +
    `<p class="total">Итого: ${money(items.reduce((a, it) => a + it.subtotal, 0))}</p>` +
    (currentUser ? `<p class="acct-hint">✓ Залогинен как ${escapeHtml(currentUser.email)} — заказ привяжется к вашему аккаунту.</p>` : "");

  // префилл данными пользователя, если вошёл
  if (currentUser) {
    const f = $("#checkout-form");
    if (!f.dataset.prefilled) {
      f.elements["name"].value = currentUser.name || "";
      f.elements["email"].value = currentUser.email || "";
      f.elements["phone"].value = currentUser.phone || "";
      f.elements["address"].value = currentUser.address || "";
      f.dataset.prefilled = "1";
    }
  }
}

$("#checkout-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const items = Object.keys(cart).map((id) => ({ product_id: Number(id), quantity: cart[id] }));

  const btn = e.target.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = "Подтверждаем...";
  setLoading(true);
  try {
    const result = await apiFetch("/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: form.get("name"),
        email: form.get("email"),
        phone: form.get("phone"),
        address: form.get("address"),
        items,
      }),
    });
    cart = {};
    updateCartBadge();
    e.target.reset();
    toast("✅ Заказ №" + result.order_id + " оформлен! Сумма: " + money(result.total_amount));
    confetti();
    showCatalog();
    loadProducts();
  } catch (err) {
    toast(err.message, false);
  } finally {
    setLoading(false);
    btn.disabled = false;
    btn.textContent = "✅ Подтвердить заказ";
  }
});

$("#go-checkout").addEventListener("click", showCheckout);

/* ---------- Конфетти ---------- */
function confetti() {
  const colors = ["#7c5cff", "#ff5f8f", "#ffb86b", "#34d399", "#20c7b0"];
  const n = 90;
  for (let i = 0; i < n; i++) {
    const p = document.createElement("div");
    p.className = "confetti";
    p.style.left = Math.random() * 100 + "vw";
    p.style.background = colors[Math.floor(Math.random() * colors.length)];
    p.style.animationDuration = Math.random() * 2 + 2 + "s";
    p.style.animationDelay = Math.random() * 0.4 + "s";
    p.style.width = p.style.height = Math.random() * 8 + 6 + "px";
    p.style.borderRadius = Math.random() > 0.5 ? "50%" : "2px";
    document.body.appendChild(p);
    setTimeout(() => p.remove(), 4400);
  }
}

/* ---------- Reveal при скролле ---------- */
const observer = new IntersectionObserver(
  (entries) => entries.forEach((en) => en.isIntersecting && en.target.classList.add("visible")),
  { threshold: 0.12 }
);
document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));

/* ---------- Хелперы без инъекций ---------- */
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeJs(s) { return String(s).replace(/'/g, "\\'").replace(/"/g, '\\"'); }
function escapeAttr(s) { return String(s).replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }

/* ---------- Экстра-анимации ---------- */
// Прелоадер: скрыть после загрузки
function initSplash() {
  const splash = $("#splash");
  window.addEventListener("load", () => {
    setTimeout(() => splash.classList.add("hide"), 400);
  });
  // страховка, если load уже прошёл
  setTimeout(() => splash.classList.add("hide"), 2500);
}

// Прогресс скролла + кнопка "наверх"
function initScrollFx() {
  const progress = $("#scroll-progress");
  const toTop = $("#to-top");
  window.addEventListener("scroll", () => {
    const scrolled = window.scrollY;
    const h = document.documentElement.scrollHeight - window.innerHeight;
    const pct = h > 0 ? (scrolled / h) * 100 : 0;
    if (progress) progress.style.width = pct + "%";
    if (toTop) toTop.classList.toggle("show", scrolled > 600);
  }, { passive: true });
  if (toTop) toTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
}

// Подсветка за курсором
function initCursorSpark() {
  const spark = $("#cursor-spark");
  if (!spark) return;
  window.addEventListener("mousemove", (e) => {
    spark.style.left = e.clientX + "px";
    spark.style.top = e.clientY + "px";
  }, { passive: true });
}

// Анимированные счётчики статистики
function animateCount(el, target, suffix = "") {
  if (!el) return;
  const dur = 1400, start = 0, startT = performance.now();
  function tick(now) {
    const p = Math.min((now - startT) / dur, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(start + (target - start) * eased) + suffix;
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}
function initCounters() {
  const books = $("#stat-books");
  const cats = $("#stat-cats");
  if (books && books.textContent !== "—") animateCount(books, Number(books.textContent));
  if (cats && cats.textContent !== "—") animateCount(cats, Number(cats.textContent));
}

// 3D-tilt карточек
function initTilt() {
  document.querySelectorAll(".product-card").forEach((card) => {
    card.addEventListener("mousemove", (e) => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      card.style.setProperty("--ry", (x * 10).toFixed(2) + "deg");
      card.style.setProperty("--rx", (-y * 10).toFixed(2) + "deg");
      card.style.setProperty("--ty", "-6px");
      card.classList.add("tilting");
    });
    card.addEventListener("mouseleave", () => {
      card.classList.remove("tilting");
      card.style.setProperty("--rx", "0deg");
      card.style.setProperty("--ry", "0deg");
      card.style.setProperty("--ty", "0px");
    });
  });
}

// Кнопка наверх + прогресс: вызвать при первом рендере товаров
function bindDynamicFx() {
  initTilt();
  initCounters();
}

/* ---------- ИИ-помощник (Bookie) ---------- */
function openAI() {
  $("#ai-chat").style.display = "flex";
  setTimeout(() => $("#ai-input").focus(), 50);
}
function closeAI() { $("#ai-chat").style.display = "none"; }

function addMsg(role, html) {
  const body = $("#chat-body");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.innerHTML = (role === "bot"
    ? '<div class="msg-av">🦉</div>'
    : '<div class="msg-av">🧑</div>') +
    '<div class="msg-bubble">' + html + "</div>";
  body.appendChild(div);
  body.scrollTop = body.scrollHeight;
  return div;
}

function addTyping() {
  const body = $("#chat-body");
  const div = document.createElement("div");
  div.className = "msg bot";
  div.innerHTML = '<div class="msg-av">🦉</div><div class="msg-bubble"><span class="typing"><span></span><span></span><span></span></span></div>';
  body.appendChild(div);
  body.scrollTop = body.scrollHeight;
  return div;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function sendAI() {
  const input = $("#ai-input");
  const q = input.value.trim();
  if (!q) return;
  addMsg("user", escapeHtml(q));
  input.value = "";
  const typing = addTyping();
  try {
    await sleep(600);
    const data = await apiFetch("/ai/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q, limit: 6 }),
    });
    typing.remove();
    const res = data.results || [];
    if (!res.length) {
      addMsg("bot", "Хм, не нашёл по запросу «" + escapeHtml(q) + "». Попробуй сформулировать иначе — например, «про космос» или «детская сказка». 🦉");
      return;
    }
    let html = "Вот что я нашёл по «" + escapeHtml(q) + "» 👇";
    html += '<div class="ai-cards">' + res.map(b => `
      <div class="ai-card">
        <div class="ai-c-ico">📖</div>
        <div class="ai-c-main">
          <div class="ai-c-name">${escapeHtml(b.name)}</div>
          <div class="ai-c-meta">${escapeHtml(b.author || "—")} · ${b.category_name ? escapeHtml(b.category_name) : ""}</div>
        </div>
        <div class="ai-c-price">${money(b.base_price)}</div>
        <button class="ai-c-add" onclick="addToCart(${b.id}, '${escapeJs(b.name)}', ${b.base_price})">В корзину</button>
      </div>`).join("") + "</div>";
    addMsg("bot", html);
  } catch (e) {
    typing.remove();
    addMsg("bot", "Упс, что-то пошло не так: " + escapeHtml(e.message));
  }
}

function askAI(q) {
  $("#ai-input").value = q;
  sendAI();
}

/* ---------- Жалоба / проблема с книгой ---------- */
let complaintProductId = null;

function openComplaint(id, name) {
  complaintProductId = id;
  $("#complaint-product").value = name || "";
  // префилл данными пользователя, если вошёл
  if (currentUser) {
    const f = $("#complaint-form");
    f.elements["name"].value = currentUser.name || "";
    f.elements["email"].value = currentUser.email || "";
    f.elements["phone"].value = currentUser.phone || "";
  }
  $("#complaint-modal").style.display = "flex";
}

function closeComplaint() {
  $("#complaint-modal").style.display = "none";
  complaintProductId = null;
}

$("#complaint-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const btn = e.target.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = "Отправляем...";
  try {
    const result = await apiFetch("/complaints", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_id: complaintProductId,
        name: form.get("name"),
        email: form.get("email"),
        phone: form.get("phone") || "",
        issue_type: form.get("issue_type"),
        description: form.get("description"),
      }),
    });
    closeComplaint();
    e.target.reset();
    toast("Заявка №" + result.id + " отправлена. Мы разберёмся!");
  } catch (err) {
    toast(err.message, false);
  } finally {
    btn.disabled = false;
    btn.textContent = "Отправить сообщение";
  }
});

/* ---------- Аналитика (владелец / разработчик / аналитик) ---------- */
let analyticsTab = "orders";
let analyticsCache = {};

function showAnalytics() {
  ["catalog", "cart", "checkout", "favorites"].forEach((id) => ($("#" + id).style.display = "none"));
  $("#analytics").style.display = "block";
  $("#analytics").classList.remove("slide-panel");
  void $("#analytics").offsetWidth;
  $("#analytics").classList.add("slide-panel");
  // привязка вкладок
  document.querySelectorAll(".analytics-tab").forEach((t) => {
    t.addEventListener("click", () => {
      analyticsTab = t.dataset.tab;
      document.querySelectorAll(".analytics-tab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      renderAnalytics();
    });
  });
  refreshAnalyticsGate();
  if (currentUser && currentUser.role === "admin") {
    if (analyticsCache[analyticsTab]) renderAnalytics();
    else loadAnalytics();
  }
}

function refreshAnalyticsGate() {
  const gate = $("#analytics-gate");
  if (!gate) return;
  const isAdmin = currentUser && currentUser.role === "admin";
  gate.style.display = isAdmin ? "none" : "block";
  const kpi = $("#analytics-kpi");
  if (kpi) kpi.style.display = isAdmin ? "block" : "none";
  const body = $("#analytics-body");
  if (body && !isAdmin) body.innerHTML = "";
}

async function loadAnalytics() {
  if (!currentUser || currentUser.role !== "admin") {
    refreshAnalyticsGate();
    return;
  }
  const errEl = $("#analytics-error");
  errEl.style.display = "none";
  const body = $("#analytics-body");
  body.innerHTML = '<div class="al-loading">Загружаем данные…</div>';
  const views = {
    orders: "/analytics/order-facts",
    products: "/analytics/product-sales",
    revenue: "/analytics/daily-revenue",
    cities: "/analytics/cities",
    reviews: "/analytics/reviews",
    events: "/analytics/event-log",
  };
  try {
    const results = await Promise.all(
      Object.entries(views).map(async ([name, url]) => {
        const data = await apiFetch(url);
        return [name, data.data !== undefined ? data.data : data];
      })
    );
    results.forEach(([name, data]) => {
      analyticsCache[name] = Array.isArray(data) ? data : (data || []);
    });
    // KPI отдельно
    const kpiData = await apiFetch("/analytics/kpi");
    analyticsCache._kpi = kpiData.data || null;
    // жалобы отдельно
    const cdata = await apiFetch("/complaints");
    analyticsCache.complaints = Array.isArray(cdata) ? cdata : [];
    renderAnalytics();
    renderKpi();
  } catch (e) {
    errEl.style.display = "block";
    errEl.textContent = "Ошибка загрузки: " + (e.message || "не удалось");
  }
}

function renderKpi() {
  const el = $("#analytics-kpi");
  if (!el) return;
  const k = analyticsCache._kpi;
  if (!k) { el.style.display = "none"; return; }
  el.style.display = "block";
  const cards = [
    { label: "Заказов", value: k.orders_total ?? 0, icon: "🛒" },
    { label: "Выручка", value: money(k.revenue_total ?? 0), icon: "💰" },
    { label: "Клиентов", value: k.customers_total ?? 0, icon: "👥" },
    { label: "Средний чек", value: money(k.avg_order ?? 0), icon: "🧾" },
    { label: "Городов", value: k.cities_total ?? 0, icon: "🏙️" },
    { label: "Отзывов", value: k.reviews_total ?? 0, icon: "⭐" },
    { label: "Открытых жалоб", value: k.complaints_open ?? 0, icon: "⚠️" },
  ];
  el.innerHTML = cards.map((c) => `
    <div class="kpi-card">
      <div class="kpi-icon">${c.icon}</div>
      <div class="kpi-value">${c.value}</div>
      <div class="kpi-label">${c.label}</div>
    </div>`).join("");
}

function renderAnalytics() {
  const body = $("#analytics-body");
  if (!currentUser || currentUser.role !== "admin") { refreshAnalyticsGate(); return; }
  const data = analyticsCache[analyticsTab] || [];
  if (!data.length) {
    body.innerHTML = '<div class="al-empty">По этому разделу пока нет данных.</div>';
    return;
  }
  if (analyticsTab === "complaints") return renderComplaints(body, data);
  if (analyticsTab === "revenue") return renderRevenue(body, data);
  if (analyticsTab === "cities") return renderCitiesTable(body, data);
  if (analyticsTab === "reviews") return renderReviewsTable(body, data);
  if (analyticsTab === "products") return renderProductsTable(body, data);
  if (analyticsTab === "events") return renderEventsTable(body, data);
  return renderOrdersTable(body, data);
}

function renderAnalyticsHeader(cols) {
  return '<tr>' + cols.map((c) => "<th>" + c + "</th>").join("") + "</tr>";
}

function renderOrdersTable(body, rows) {
  const cols = ["Заказ", "Статус", "Покупатель", "Дата", "Товаров", "Сумма"];
  const trs = rows.map((r) => `<tr>
    <td>#${r.order_id}</td>
    <td><span class="status-badge st-${(r.status || "").replace(" ", "-")}">${escapeHtml(r.status)}</span></td>
    <td>${escapeHtml(r.customer_email || "—")}</td>
    <td>${escapeHtml(r.order_date || "")}</td>
    <td>${r.items_count ?? "-"}</td>
    <td>${money(r.total_amount)}</td>
  </tr>`).join("");
  body.innerHTML = '<table class="al-table"><thead>' + renderAnalyticsHeader(cols) + '</thead><tbody>' + trs + '</tbody></table>';
}

function renderProductsTable(body, rows) {
  const cols = ["Товар", "Категория", "Заказ", "Кол-во", "Цена", "Сумма"];
  const trs = rows.slice(0, 50).map((r) => `<tr>
    <td>${escapeHtml(r.product_name)}</td>
    <td>${escapeHtml(r.category_name || "—")}</td>
    <td>#${r.order_id}</td>
    <td>${r.quantity}</td>
    <td>${money(r.unit_price)}</td>
    <td>${money(r.line_total)}</td>
  </tr>`).join("");
  body.innerHTML = '<table class="al-table"><thead>' + renderAnalyticsHeader(cols) + '</thead><tbody>' + trs + '</tbody></table>';
}

function renderRevenue(body, rows) {
  const cols = ["Дата", "Заказов", "Покупателей", "Выручка", "Средний чек"];
  const trs = rows.map((r) => `<tr>
    <td>${escapeHtml(r.revenue_date)}</td>
    <td>${r.orders_count}</td>
    <td>${r.customers_count}</td>
    <td>${money(r.revenue)}</td>
    <td>${money(r.avg_order_value)}</td>
  </tr>`).join("");
  body.innerHTML = '<table class="al-table"><thead>' + renderAnalyticsHeader(cols) + '</thead><tbody>' + trs + '</tbody></table>';
}

function renderCitiesTable(body, rows) {
  const cols = ["Город", "Заказов", "Покупателей", "Выручка"];
  const trs = rows.map((r) => `<tr>
    <td><span class="city-dot">📍</span> ${escapeHtml(r.city)}</td>
    <td>${r.orders_count}</td>
    <td>${r.customers_count}</td>
    <td>${money(r.revenue)}</td>
  </tr>`).join("");
  body.innerHTML = '<table class="al-table"><thead>' + renderAnalyticsHeader(cols) + '</thead><tbody>' + trs + '</tbody></table>';
}

function renderReviewsTable(body, rows) {
  const cols = ["Книга", "Пользователь", "Оценка", "Отзыв", "Дата"];
  const trs = rows.map((r) => `<tr>
    <td>${escapeHtml(r.product_name)}</td>
    <td>${escapeHtml(r.user_name || "—")}</td>
    <td><span class="stars">${renderStars(r.rating)}</span></td>
    <td>${escapeHtml(r.text || "—")}</td>
    <td>${escapeHtml(r.created_at || "")}</td>
  </tr>`).join("");
  body.innerHTML = '<table class="al-table"><thead>' + renderAnalyticsHeader(cols) + '</thead><tbody>' + trs + '</tbody></table>';
}

function renderStars(rating) {
  const r = Math.max(1, Math.min(5, Number(rating) || 1));
  let s = "";
  for (let i = 1; i <= 5; i++) s += i <= r ? "★" : "☆";
  return s;
}

function renderEventsTable(body, rows) {
  const cols = ["Событие", "Дата", "Пользователь", "Товар", "Заказ", "Значение", "Мета"];
  const trs = rows.slice(0, 80).map((r) => `<tr>
    <td>${escapeHtml(r.event_type)}</td>
    <td>${escapeHtml(r.created_at || "")}</td>
    <td>${r.user_id ?? "-"}</td>
    <td>${r.product_id ?? "-"}</td>
    <td>${r.order_id ?? "-"}</td>
    <td>${r.value != null ? money(r.value) : "-"}</td>
    <td>${escapeHtml(r.meta || "")}</td>
  </tr>`).join("");
  body.innerHTML = '<table class="al-table"><thead>' + renderAnalyticsHeader(cols) + '</thead><tbody>' + trs + '</tbody></table>';
}

function renderComplaints(body, rows) {
  const cols = ["ID", "Книга", "Тип", "Клиент", "Email", "Описание", "Статус", "Дата"];
  const trs = rows.map((r) => `<tr>
    <td>#${r.id}</td>
    <td>${escapeHtml(r.product_name || "—")}</td>
    <td>${escapeHtml(r.issue_type)}</td>
    <td>${escapeHtml(r.name)}</td>
    <td>${escapeHtml(r.email)}</td>
    <td>${escapeHtml(r.description)}</td>
    <td><span class="status-badge st-${(r.status || "").replace(" ", "-")}">${escapeHtml(r.status)}</span></td>
    <td>${escapeHtml(r.created_at || "")}</td>
  </tr>`).join("");
  body.innerHTML = '<table class="al-table"><thead>' + renderAnalyticsHeader(cols) + '</thead><tbody>' + trs + '</tbody></table>';
}

/* ---------- Инициализация ---------- */
loadCategories();
loadProducts();
checkAuth();
loadFavorites();
initSplash();
initScrollFx();
initCursorSpark();
// появление страницы
document.body.classList.add("ready");
// показать reveal-элементы, которые уже в зоне видимости
setTimeout(() => document.querySelectorAll(".reveal").forEach((el) => el.classList.add("visible")), 400);