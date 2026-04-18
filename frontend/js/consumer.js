// consumer.js — Consumer feed: browse, search, view, comment, rate
// TODO Phase 2: Wire to real API endpoints

let currentPhotoId = null;
let currentPage = 1;
const PAGE_SIZE = 12;
let searchQuery = '';

document.addEventListener('DOMContentLoaded', () => {
  const user = requireAuth('consumer');
  if (!user) return;
  document.getElementById('nav-username').textContent = user.name;
  loadPhotos(true);
  setupStarRating();
});

async function loadPhotos(reset = false) {
  if (reset) { currentPage = 1; }
  const grid = document.getElementById('photos-grid');
  if (reset) grid.innerHTML = '<p class="placeholder-text">Loading...</p>';

  const params = new URLSearchParams({ page: currentPage, limit: PAGE_SIZE });
  if (searchQuery) params.set('q', searchQuery);

  try {
    const res = await fetch(`${API_BASE}/photos?${params}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.message);
    const photos = data.photos || [];
    if (reset) grid.innerHTML = '';
    renderFeed(grid, photos);
    const loadMoreBtn = document.getElementById('load-more-btn');
    loadMoreBtn.classList.toggle('hidden', photos.length < PAGE_SIZE);
  } catch (err) {
    grid.innerHTML = `<p class="placeholder-text">Could not load photos: ${err.message}</p>`;
  }
}

function loadMore() {
  currentPage++;
  loadPhotos(false);
}

function handleSearch(event) {
  event.preventDefault();
  searchQuery = document.getElementById('search-input').value.trim();
  loadPhotos(true);
}

function renderFeed(container, photos) {
  if (!photos.length && container.children.length === 0) {
    container.innerHTML = '<p class="placeholder-text">No photos found.</p>';
    return;
  }
  photos.forEach(p => {
    const card = document.createElement('div');
    card.className = 'photo-card';
    card.onclick = () => openModal(p.id);
    card.innerHTML = `
      <img src="${p.imageUrl}" alt="${p.title}" loading="lazy" />
      <div class="photo-card-body">
        <h3>${p.title}</h3>
        <p class="meta">${p.location || ''}</p>
        <p class="meta">&#9733; ${p.avgRating ? p.avgRating.toFixed(1) : '—'}</p>
      </div>`;
    container.appendChild(card);
  });
}

async function openModal(photoId) {
  currentPhotoId = photoId;
  const modal = document.getElementById('photo-modal');
  modal.classList.remove('hidden');
  document.getElementById('modal-img').src = '';
  document.getElementById('comments-list').innerHTML = '';
  document.getElementById('avg-rating').textContent = '';
  resetStars();

  try {
    const [photoRes, commentsRes] = await Promise.all([
      fetch(`${API_BASE}/photos/${photoId}`),
      fetch(`${API_BASE}/photos/${photoId}/comments`),
    ]);
    const photo = await photoRes.json();
    const commentsData = await commentsRes.json();

    document.getElementById('modal-img').src = photo.imageUrl;
    document.getElementById('modal-img').alt = photo.title;
    document.getElementById('modal-title').textContent = photo.title;
    document.getElementById('modal-caption').textContent = photo.caption || '';
    document.getElementById('modal-location').textContent = photo.location ? `📍 ${photo.location}` : '';
    document.getElementById('modal-people').textContent = photo.people?.length ? `👥 ${photo.people.join(', ')}` : '';
    document.getElementById('modal-creator').textContent = `By ${photo.creatorName}`;
    document.getElementById('avg-rating').textContent = photo.avgRating
      ? `Avg: ${photo.avgRating.toFixed(1)} / 5`
      : 'No ratings yet';

    renderComments(commentsData.comments || []);
  } catch (err) {
    console.error('Failed to load photo detail:', err);
  }
}

function closeModal(event) {
  if (!event || event.target.id === 'photo-modal' || event.currentTarget?.classList.contains('modal-close')) {
    document.getElementById('photo-modal').classList.add('hidden');
    currentPhotoId = null;
  }
}

function renderComments(comments) {
  const list = document.getElementById('comments-list');
  list.innerHTML = comments.length
    ? comments.map(c => `
        <div class="comment-item">
          <div class="comment-author">${c.authorName}</div>
          <div>${c.text}</div>
        </div>`).join('')
    : '<p class="placeholder-text">No comments yet.</p>';
}

async function submitComment(event) {
  event.preventDefault();
  const text = document.getElementById('comment-text').value.trim();
  if (!text || !currentPhotoId) return;

  try {
    const res = await fetch(`${API_BASE}/photos/${currentPhotoId}/comments`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message);
    document.getElementById('comment-text').value = '';
    const commentsRes = await fetch(`${API_BASE}/photos/${currentPhotoId}/comments`);
    const commentsData = await commentsRes.json();
    renderComments(commentsData.comments || []);
  } catch (err) {
    alert(`Comment failed: ${err.message}`);
  }
}

function setupStarRating() {
  const stars = document.querySelectorAll('.star');
  stars.forEach(star => {
    star.addEventListener('mouseover', () => highlightStars(star.dataset.value));
    star.addEventListener('mouseout', resetStars);
    star.addEventListener('click', () => submitRating(star.dataset.value));
  });
}

function highlightStars(upTo) {
  document.querySelectorAll('.star').forEach(s => {
    s.classList.toggle('active', parseInt(s.dataset.value) <= parseInt(upTo));
  });
}

function resetStars() {
  document.querySelectorAll('.star').forEach(s => s.classList.remove('active'));
}

async function submitRating(value) {
  if (!currentPhotoId) return;
  try {
    const res = await fetch(`${API_BASE}/photos/${currentPhotoId}/ratings`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating: parseInt(value) }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message);
    document.getElementById('avg-rating').textContent = data.avgRating
      ? `Avg: ${data.avgRating.toFixed(1)} / 5`
      : 'Rated!';
    highlightStars(value);
  } catch (err) {
    alert(`Rating failed: ${err.message}`);
  }
}
