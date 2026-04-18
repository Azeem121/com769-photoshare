# REST API Specification — PhotoShare

Base URL (local): `http://localhost:7071/api`  
Base URL (production): `https://<func-app>.azurewebsites.net/api`

---

## Authentication

All protected endpoints require:
```
Authorization: Bearer <jwt-token>
```

---

## POST /users/register
Register a new **consumer** account.

**Body**
```json
{ "name": "Alice", "email": "alice@example.com", "password": "secret123" }
```
**Response 201**
```json
{ "token": "<jwt>", "role": "consumer", "name": "Alice" }
```

---

## POST /users/login
**Body**
```json
{ "email": "alice@example.com", "password": "secret123" }
```
**Response 200**
```json
{ "token": "<jwt>", "role": "consumer|creator", "name": "Alice" }
```

---

## POST /photos — (Creator only)
Upload a photo with metadata. `multipart/form-data`.

| Field | Type | Required |
|-------|------|----------|
| photo | file (image/*) | Yes |
| title | string | Yes |
| caption | string | No |
| location | string | No |
| people | JSON array string | No |

**Response 201**
```json
{ "id": "uuid", "imageUrl": "https://..." }
```

---

## GET /photos
List photos with optional search. Public.

**Query params**
| Param | Description |
|-------|-------------|
| q | Search in title, caption, location, people |
| page | Page number (default 1) |
| limit | Items per page (default 12, max 50) |
| mine | `true` = only return calling creator's photos |

**Response 200**
```json
{
  "photos": [{ "id": "...", "title": "...", "imageUrl": "...", "location": "...", "avgRating": 4.2 }],
  "total": 100,
  "page": 1
}
```

---

## GET /photos/{id}
Get full photo detail. Public.

**Response 200**
```json
{
  "id": "uuid",
  "title": "Sunset",
  "caption": "Beautiful evening",
  "location": "Belfast",
  "people": ["Bob", "Carol"],
  "imageUrl": "https://...",
  "creatorName": "Alice",
  "avgRating": 4.2,
  "ratingCount": 17,
  "createdAt": "2025-01-01T12:00:00Z"
}
```

---

## GET /photos/{id}/comments
**Response 200**
```json
{ "comments": [{ "id": "...", "authorName": "Bob", "text": "Great!", "createdAt": "..." }] }
```

---

## POST /photos/{id}/comments — (Consumer only)
**Body**
```json
{ "text": "Lovely photo!" }
```
**Response 201**
```json
{ "id": "uuid", "authorName": "Bob", "text": "Lovely photo!", "createdAt": "..." }
```

---

## POST /photos/{id}/ratings — (Consumer only)
**Body**
```json
{ "rating": 4 }
```
**Response 200**
```json
{ "avgRating": 4.3, "ratingCount": 18 }
```

---

## Error Format
All errors follow:
```json
{ "message": "Human-readable error description" }
```
