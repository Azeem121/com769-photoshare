// auth.js — Login, register, token management, and route guarding
// TODO Phase 2: Replace API_BASE with deployed Function App URL
const API_BASE = window.location.hostname === 'localhost'
  ? 'http://localhost:7071/api'
  : '/api';

function showTab(tab) {
  document.getElementById('form-login').classList.toggle('hidden', tab !== 'login');
  document.getElementById('form-register').classList.toggle('hidden', tab !== 'register');
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
}

async function handleLogin(event) {
  event.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const errEl = document.getElementById('login-error');
  errEl.textContent = '';

  try {
    const res = await fetch(`${API_BASE}/users/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || 'Login failed');
    localStorage.setItem('token', data.token);
    localStorage.setItem('role', data.role);
    localStorage.setItem('name', data.name);
    redirectByRole(data.role);
  } catch (err) {
    errEl.textContent = err.message;
  }
}

async function handleRegister(event) {
  event.preventDefault();
  const name = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const errEl = document.getElementById('register-error');
  errEl.textContent = '';

  try {
    const res = await fetch(`${API_BASE}/users/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password, role: 'consumer' }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || 'Registration failed');
    localStorage.setItem('token', data.token);
    localStorage.setItem('role', data.role);
    localStorage.setItem('name', data.name);
    redirectByRole(data.role);
  } catch (err) {
    errEl.textContent = err.message;
  }
}

function redirectByRole(role) {
  if (role === 'creator') {
    window.location.href = '/pages/creator.html';
  } else {
    window.location.href = '/pages/consumer.html';
  }
}

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('name');
  window.location.href = '/index.html';
}

function requireAuth(requiredRole) {
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role');
  if (!token) {
    window.location.href = '/index.html';
    return null;
  }
  if (requiredRole && role !== requiredRole) {
    window.location.href = '/index.html';
    return null;
  }
  return { token, role, name: localStorage.getItem('name') };
}

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem('token')}` };
}
