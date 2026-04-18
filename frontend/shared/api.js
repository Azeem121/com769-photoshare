/**
 * api.js — All backend REST calls
 *
 * Azure SWA proxies /api/* to the Function App automatically.
 * Cookies (including the SWA auth session) are sent with every request
 * so we do NOT need to attach any Authorization header manually — the
 * x-ms-client-principal header is injected by the SWA runtime.
 */

const API = "/api";

async function _request(method, path, body = null, isFormData = false) {
  const options = {
    method,
    credentials: "include",
  };

  if (body !== null) {
    if (isFormData) {
      options.body = body; // FormData — browser sets Content-Type with boundary
    } else {
      options.headers = { "Content-Type": "application/json" };
      options.body = JSON.stringify(body);
    }
  }

  const res = await fetch(`${API}${path}`, options);

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

// ── Health ────────────────────────────────────────────────────────────────────
const getHealth = () => _request("GET", "/health");

// ── Photos (public) ───────────────────────────────────────────────────────────
/**
 * @param {{ search?: string, sort?: string, tag?: string, page?: number, limit?: number }} opts
 */
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

/**
 * @param {FormData} formData  - must include: photo (File), title, caption?, location?, people?
 */
const uploadPhoto = (formData) => _request("POST", "/photos/upload", formData, true);

const deletePhoto = (id) => _request("DELETE", `/photos/${id}`);

// ── Comments ──────────────────────────────────────────────────────────────────
const addComment = (photoId, text) =>
  _request("POST", `/photos/${photoId}/comment`, { text });

// ── Ratings ───────────────────────────────────────────────────────────────────
const ratePhoto = (photoId, rating) =>
  _request("POST", `/photos/${photoId}/rate`, { rating });
