/**
 * auth.js — Token-based authentication helper
 *
 * Tokens and user info are stored in localStorage.
 * Use @creator suffix in username for creator access (e.g. "alice@creator").
 */

const PS_TOKEN_KEY = "ps_token";
const PS_USER_KEY  = "ps_user";

function getToken() {
  return localStorage.getItem(PS_TOKEN_KEY);
}

function getUser() {
  const raw = localStorage.getItem(PS_USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

function saveSession(token, user) {
  localStorage.setItem(PS_TOKEN_KEY, token);
  localStorage.setItem(PS_USER_KEY, JSON.stringify(user));
}

function clearSession() {
  localStorage.removeItem(PS_TOKEN_KEY);
  localStorage.removeItem(PS_USER_KEY);
}

function logout() {
  clearSession();
  window.location.href = "/index.html";
}

/**
 * Require authentication; optionally restrict to a role.
 * Redirects to index.html if not authenticated or wrong role.
 * Returns the user object if authorised.
 */
function requireAuth(requiredRole) {
  const token = getToken();
  const user  = getUser();

  if (!token || !user) {
    window.location.href = "/index.html";
    return null;
  }

  if (requiredRole && user.role !== requiredRole) {
    window.location.href = user.role === "creator" ? "/creator.html" : "/consumer.html";
    return null;
  }

  return user;
}

/** Redirect already-logged-in users to their dashboard. */
function redirectIfLoggedIn() {
  const user = getUser();
  if (!user) return;
  if (user.role === "creator") {
    window.location.href = "/creator.html";
  } else {
    window.location.href = "/consumer.html";
  }
}

/** Populate the navbar username element. */
function setNavUser(user) {
  const el = document.getElementById("nav-username");
  if (el && user) el.textContent = user.username || "User";
}
