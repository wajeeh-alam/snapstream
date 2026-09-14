const state = {
  token: localStorage.getItem("snapstream_token"),
  user: JSON.parse(localStorage.getItem("snapstream_user") || "null"),
  feed: "recent",
  liked: new Set(JSON.parse(localStorage.getItem("snapstream_liked") || "[]")),
  following: new Set(JSON.parse(localStorage.getItem("snapstream_following") || "[]")),
  authMode: "login",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value) => {
  const node = document.createElement("span");
  node.textContent = value || "";
  return node.innerHTML;
};

async function api(path, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body && typeof options.body !== "string") {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}

function initials(name) {
  return name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2);
}

function avatarStyle(id) {
  let hash = 0;
  for (const character of id) hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0;
  const hue = Math.abs(hash) % 360;
  return `background:linear-gradient(135deg,hsl(${hue} 52% 47%),hsl(${(hue + 48) % 360} 68% 67%))`;
}

function relativeTime(value) {
  const seconds = Math.max(1, Math.floor((Date.now() - new Date(value)) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

let toastTimer;
function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 2600);
}

function requireAuth() {
  if (state.token) return true;
  openAuth();
  return false;
}

function renderSession() {
  const loggedIn = Boolean(state.token && state.user);
  $("#composer").classList.toggle("authenticated", loggedIn);
  $("#session-name").textContent = loggedIn ? state.user.display_name : "Guest explorer";
  $("#session-handle").textContent = loggedIn ? `@${state.user.username}` : "Sign in to interact";
  $("#session-avatar").textContent = loggedIn ? initials(state.user.display_name) : "S";
  $("#composer-avatar").textContent = loggedIn ? initials(state.user.display_name) : "+";
  $("#session-action").title = loggedIn ? "Sign out" : "Sign in";
  $("#mobile-auth").textContent = loggedIn ? "Sign out" : "Sign in";
  $("#rail-auth").textContent = loggedIn ? `Signed in as @${state.user.username}` : "Sign in to demo";
}

function setSession(session) {
  state.token = session?.access_token || null;
  state.user = session?.user || null;
  if (state.token) {
    localStorage.setItem("snapstream_token", state.token);
    localStorage.setItem("snapstream_user", JSON.stringify(state.user));
  } else {
    localStorage.removeItem("snapstream_token");
    localStorage.removeItem("snapstream_user");
  }
  renderSession();
}

function openAuth() {
  $("#auth-error").textContent = "";
  $("#auth-dialog").showModal();
  setTimeout(() => $("#login").focus(), 50);
}

function setAuthMode(mode) {
  state.authMode = mode;
  $$('[data-auth-mode]').forEach((button) => button.classList.toggle("active", button.dataset.authMode === mode));
  $$(".register-only").forEach((element) => element.classList.toggle("hidden", mode !== "register"));
  $$(".login-only").forEach((element) => element.classList.toggle("hidden", mode === "register"));
  $("#auth-title").textContent = mode === "login" ? "Sign in to the stream" : "Make the stream yours";
  $("#auth-submit").textContent = mode === "login" ? "Sign in" : "Create account";
  $("#email").required = mode === "register";
  $("#display-name").required = mode === "register";
}

async function submitAuth(event) {
  event.preventDefault();
  const submit = $("#auth-submit");
  submit.disabled = true;
  $("#auth-error").textContent = "";
  const login = $("#login").value.trim();
  try {
    const session = state.authMode === "login"
      ? await api("/auth/login", { method: "POST", body: { login, password: $("#password").value } })
      : await api("/auth/register", { method: "POST", body: {
          username: login,
          email: $("#email").value.trim(),
          display_name: $("#display-name").value.trim(),
          password: $("#password").value,
        }});
    setSession(session);
    $("#auth-dialog").close();
    toast(`Welcome, ${session.user.display_name}`);
    await loadPeople();
  } catch (error) {
    $("#auth-error").textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}

async function signOut() {
  if (state.token) {
    await api("/auth/logout", { method: "POST" }).catch(() => null);
    setSession(null);
    toast("Signed out");
  } else openAuth();
}

async function loadFeed() {
  const feed = $("#feed");
  feed.setAttribute("aria-busy", "true");
  try {
    const data = await api(`/feed?kind=${state.feed}&limit=30`);
    $("#post-count").textContent = data.items.length;
    $("#mode-label").textContent = state.feed.toUpperCase();
    feed.innerHTML = data.items.length
      ? data.items.map(postTemplate).join("")
      : '<div class="empty">No stories yet. Be the first to share one.</div>';
    await hydrateMedia(data.items);
  } catch (error) {
    feed.innerHTML = `<div class="empty">Could not load the stream.<br>${escapeHtml(error.message)}</div>`;
  } finally {
    feed.removeAttribute("aria-busy");
  }
}

function postTemplate(post, index) {
  const mine = state.user?.id === post.author.id;
  const following = state.following.has(post.author.id);
  const liked = state.liked.has(post.id);
  const media = post.media
    ? `<div class="media-placeholder" data-media-id="${post.id}">Loading private media…</div>` : "";
  return `<article class="post-card" style="animation-delay:${Math.min(index, 8) * 35}ms">
    <div class="post-content">
      <div class="post-head">
        <div class="avatar small" style="${avatarStyle(post.author.id)}">${escapeHtml(initials(post.author.display_name))}</div>
        <div class="post-author"><strong>${escapeHtml(post.author.display_name)}</strong><span>@${escapeHtml(post.author.username)}</span></div>
        ${mine ? "" : `<button class="follow-button ${following ? "following" : ""}" data-follow="${post.author.id}">${following ? "Following" : "+ Follow"}</button>`}
      </div>
      ${post.body ? `<p class="post-body">${escapeHtml(post.body)}</p>` : ""}
    </div>
    ${media}
    <div class="post-actions">
      <button class="action-button ${liked ? "liked" : ""}" data-like="${post.id}"><span class="heart">${liked ? "♥" : "♡"}</span><span data-like-count>${post.likes_count}</span></button>
      <button class="action-button" data-copy="${post.id}">⌁ Share</button>
      <span class="post-time">${relativeTime(post.created_at)}</span>
    </div>
  </article>`;
}

async function hydrateMedia(posts) {
  await Promise.all(posts.filter((post) => post.media).map(async (post) => {
    const placeholder = document.querySelector(`[data-media-id="${post.id}"]`);
    if (!placeholder) return;
    try {
      const result = await api(`/posts/${post.id}/media-url`);
      const element = document.createElement(post.media.content_type.startsWith("video/") ? "video" : "img");
      element.className = "post-media";
      element.src = result.download_url;
      element.alt = post.body ? `Media shared with: ${post.body}` : "SnapStream post media";
      if (element.tagName === "VIDEO") { element.controls = true; element.preload = "metadata"; }
      placeholder.replaceWith(element);
    } catch { placeholder.textContent = "Media temporarily unavailable"; }
  }));
}

async function toggleLike(button) {
  if (!requireAuth()) return;
  const postId = button.dataset.like;
  const wasLiked = state.liked.has(postId);
  button.disabled = true;
  try {
    const result = await api(`/posts/${postId}/likes`, { method: wasLiked ? "DELETE" : "POST" });
    if (result.liked) state.liked.add(postId); else state.liked.delete(postId);
    localStorage.setItem("snapstream_liked", JSON.stringify([...state.liked]));
    button.classList.toggle("liked", result.liked);
    button.querySelector(".heart").textContent = result.liked ? "♥" : "♡";
    button.querySelector("[data-like-count]").textContent = result.likes_count;
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
}

async function toggleFollow(userId) {
  if (!requireAuth()) return;
  const wasFollowing = state.following.has(userId);
  try {
    const result = await api(`/users/${userId}/follow`, { method: wasFollowing ? "DELETE" : "POST" });
    if (result.following) state.following.add(userId); else state.following.delete(userId);
    localStorage.setItem("snapstream_following", JSON.stringify([...state.following]));
    $$(`[data-follow="${userId}"]`).forEach((button) => {
      button.classList.toggle("following", result.following);
      button.textContent = result.following ? "Following" : "+ Follow";
    });
  } catch (error) { toast(error.message); }
}

async function loadPeople() {
  try {
    const users = (await api("/users?limit=6")).filter((user) => user.id !== state.user?.id).slice(0, 4);
    $("#people-list").innerHTML = users.map((user) => `<div class="person">
      <div class="avatar small" style="${avatarStyle(user.id)}">${escapeHtml(initials(user.display_name))}</div>
      <div class="person-copy"><strong>${escapeHtml(user.display_name)}</strong><span>@${escapeHtml(user.username)}</span></div>
      <button data-follow="${user.id}" class="${state.following.has(user.id) ? "following" : ""}">${state.following.has(user.id) ? "Following" : "+ Follow"}</button>
    </div>`).join("") || '<p class="muted">No creators yet.</p>';
  } catch { $("#people-list").innerHTML = '<p class="muted">Creators unavailable.</p>'; }
}

async function submitPost(event) {
  event.preventDefault();
  if (!requireAuth()) return;
  const button = event.currentTarget.querySelector("button[type=submit]");
  const body = $("#post-body").value.trim();
  const file = $("#post-media").files[0];
  if (!body && !file) return toast("Add a caption or choose media first.");
  button.disabled = true;
  button.textContent = "Sharing…";
  try {
    let media = null;
    if (file) {
      const presigned = await api("/uploads/presign", { method: "POST", body: {
        filename: file.name, content_type: file.type, size_bytes: file.size,
      }});
      const uploadHeaders = { ...presigned.headers };
      delete uploadHeaders["Content-Length"];
      const uploaded = await fetch(presigned.upload_url, { method: "PUT", headers: uploadHeaders, body: file });
      if (!uploaded.ok) throw new Error("Media upload failed");
      media = { key: presigned.key, content_type: file.type, size_bytes: file.size };
    }
    await api("/posts", { method: "POST", body: { body, media } });
    event.currentTarget.reset();
    $("#file-name").textContent = "";
    toast("Post shared");
    state.feed = "recent";
    updateFeedControls();
    await loadFeed();
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; button.innerHTML = "Share post <span>↗</span>"; }
}

function updateFeedControls() {
  $$('[data-feed]').forEach((button) => button.classList.toggle("active", button.dataset.feed === state.feed));
}

async function checkHealth() {
  try {
    await api("/health/ready");
    $("#system-status").textContent = "All systems ready";
    $(".status-dot")?.classList.add("ready");
  } catch { $("#system-status").textContent = "Service degraded"; }
}

document.addEventListener("click", (event) => {
  const feedButton = event.target.closest("[data-feed]");
  if (feedButton) { state.feed = feedButton.dataset.feed; updateFeedControls(); loadFeed(); }
  const likeButton = event.target.closest("[data-like]");
  if (likeButton) toggleLike(likeButton);
  const followButton = event.target.closest("[data-follow]");
  if (followButton) toggleFollow(followButton.dataset.follow);
  const copyButton = event.target.closest("[data-copy]");
  if (copyButton) navigator.clipboard?.writeText(`${location.origin}/#post-${copyButton.dataset.copy}`).then(() => toast("Link copied"));
});

$("#auth-form").addEventListener("submit", submitAuth);
$("#post-form").addEventListener("submit", submitPost);
$("#dialog-close").addEventListener("click", () => $("#auth-dialog").close());
$$('[data-auth-mode]').forEach((button) => button.addEventListener("click", () => setAuthMode(button.dataset.authMode)));
$("#composer-lock").addEventListener("click", openAuth);
$("#rail-auth").addEventListener("click", () => state.token ? null : openAuth());
$("#session-action").addEventListener("click", signOut);
$("#mobile-auth").addEventListener("click", signOut);
$("#refresh-feed").addEventListener("click", loadFeed);
$("#post-media").addEventListener("change", (event) => { $("#file-name").textContent = event.target.files[0]?.name || ""; });

renderSession();
setAuthMode("login");
Promise.all([loadFeed(), loadPeople(), checkHealth()]);
