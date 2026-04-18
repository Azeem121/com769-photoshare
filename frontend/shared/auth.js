/**
 * auth.js — Azure Static Web Apps authentication helper
 *
 * Calls /.auth/me to get the current user and their roles.
 * Exported functions are used by every page to guard access and
 * populate the navbar.
 */

const AUTH_ME_URL = "/.auth/me";

/**
 * Fetch the current user from Azure SWA.
 * Returns null when not logged in.
 * @returns {Promise<{userId:string, userDetails:string, userRoles:string[]}|null>}
 */
async function getCurrentUser() {
  try {
    const res = await fetch(AUTH_ME_URL);
    if (!res.ok) return null;
    const data = await res.json();
    const principal = data.clientPrincipal;
    return principal && principal.userId ? principal : null;
  } catch {
    return null;
  }
}

/**
 * Require authentication and redirect unauthenticated users to index.html.
 * Optionally restrict to a specific role (e.g. "creator" or "consumer").
 * Returns the principal object.
 */
async function requireAuth(requiredRole = null) {
  const user = await getCurrentUser();

  if (!user) {
    window.location.href = "/index.html";
    return null;
  }

  if (requiredRole && !user.userRoles.includes(requiredRole)) {
    // Wrong role — redirect to correct page
    if (user.userRoles.includes("creator")) {
      window.location.href = "/creator.html";
    } else {
      window.location.href = "/consumer.html";
    }
    return null;
  }

  return user;
}

/**
 * Redirect a logged-in user to the correct role page.
 * Used on index.html after login.
 */
async function redirectIfLoggedIn() {
  const user = await getCurrentUser();
  if (!user) return;
  if (user.userRoles.includes("creator")) {
    window.location.href = "/creator.html";
  } else if (user.userRoles.includes("consumer")) {
    window.location.href = "/consumer.html";
  }
}

/** Populate a navbar element with the user's display name. */
function setNavUser(user) {
  const el = document.getElementById("nav-username");
  if (el && user) el.textContent = user.userDetails || "User";
}

/** Trigger Azure SWA logout. */
function logout() {
  window.location.href = "/.auth/logout?post_logout_redirect_uri=/index.html";
}
