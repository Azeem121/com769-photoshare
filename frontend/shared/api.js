/**
 * api.js — All backend REST calls
 *
 * Uses Bearer token from localStorage for authenticated requests.
 */

const API_BASE = "https://photoshareapi-cpechycedwbecjae.francecentral-01.azurewebsites.net/api";

function authHeaders() {
  const token = getToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
}

async function _request(method, path, body = null, isFormData = false) {
  const headers = { ...authHeaders() };

  const options = { method, headers };

  if (body !== null) {
    if (isFormData) {
      options.body = body;
    } else {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
  }

  const res = await fetch(`${API_BASE}${path}`, options);

  if (res.status === 401) {
    clearSession();
    window.location.href = "/index.html";
    return null;
  }

  if (res.status === 204) return null;

  let data;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const msg = data?.error || data?.message || `HTTP ${res.status}`;
    throw new Error(msg);
  }

  return data;
}

// ── Auth ──────────────────────────────────────────────────────────────────────
const login = (username, password) =>
  _request("POST", "/auth/login", { username, password });

// ── Health ────────────────────────────────────────────────────────────────────
const getHealth = () => _request("GET", "/health");

// ── Photos (public) ───────────────────────────────────────────────────────────
function listPhotos({ search = "", sort = "recent", tag = "", page = 1, limit = 12 } = {}) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (sort && sort !== "recent") params.set("sort", sort);
  if (tag) params.set("tag", tag);
  params.set("page", page);
  params.set("limit", limit);
  const qs = params.toString();
  return _request("GET", `/photos${qs ? "?" + qs : ""}`);
}

const getPhoto = (id) => _request("GET", `/photos/${id}`);

// ── Photos (creator) ─────────────────────────────────────────────────────────
const getMyPhotos = () => _request("GET", "/photos/my");

const uploadPhoto = (formData) => _request("POST", "/photos/upload", formData, true);

const deletePhoto = (id) => _request("DELETE", `/photos/${id}`);

// ── Comments ──────────────────────────────────────────────────────────────────
const addComment = (photoId, text) =>
  _request("POST", `/photos/${photoId}/comment`, { text });

// ── Ratings ───────────────────────────────────────────────────────────────────
const ratePhoto = (photoId, rating) =>
  _request("POST", `/photos/${photoId}/rate`, { rating });
