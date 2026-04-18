// creator.js — Creator dashboard: upload photo + view own uploads
// TODO Phase 2: Wire to real API endpoints

document.addEventListener('DOMContentLoaded', () => {
  const user = requireAuth('creator');
  if (!user) return;
  document.getElementById('nav-username').textContent = user.name;
  loadMyPhotos();
});

function previewPhoto(event) {
  const file = event.target.files[0];
  if (!file) return;
  const preview = document.getElementById('photo-preview');
  preview.src = URL.createObjectURL(file);
  preview.classList.remove('hidden');
}

async function handleUpload(event) {
  event.preventDefault();
  const btn = document.getElementById('upload-btn');
  const statusEl = document.getElementById('upload-status');
  btn.disabled = true;
  statusEl.textContent = 'Uploading...';

  const file = document.getElementById('photo-file').files[0];
  const title = document.getElementById('photo-title').value.trim();
  const caption = document.getElementById('photo-caption').value.trim();
  const location = document.getElementById('photo-location').value.trim();
  const people = document.getElementById('photo-people').value
    .split(',').map(p => p.trim()).filter(Boolean);

  const formData = new FormData();
  formData.append('photo', file);
  formData.append('title', title);
  formData.append('caption', caption);
  formData.append('location', location);
  formData.append('people', JSON.stringify(people));

  try {
    const res = await fetch(`${API_BASE}/photos`, {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || 'Upload failed');
    statusEl.textContent = 'Photo uploaded successfully!';
    document.getElementById('upload-form').reset();
    document.getElementById('photo-preview').classList.add('hidden');
    loadMyPhotos();
  } catch (err) {
    statusEl.textContent = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

async function loadMyPhotos() {
  const grid = document.getElementById('my-photos-grid');
  grid.innerHTML = '<p class="placeholder-text">Loading...</p>';
  try {
    const res = await fetch(`${API_BASE}/photos?mine=true`, {
      headers: authHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message);
    renderPhotoGrid(grid, data.photos || []);
  } catch (err) {
    grid.innerHTML = `<p class="placeholder-text">Could not load photos: ${err.message}</p>`;
  }
}

function renderPhotoGrid(container, photos) {
  if (!photos.length) {
    container.innerHTML = '<p class="placeholder-text">No photos yet. Upload your first one!</p>';
    return;
  }
  container.innerHTML = photos.map(p => `
    <div class="photo-card">
      <img src="${p.imageUrl}" alt="${p.title}" loading="lazy" />
      <div class="photo-card-body">
        <h3>${p.title}</h3>
        <p class="meta">${p.location || ''}</p>
      </div>
    </div>
  `).join('');
}
