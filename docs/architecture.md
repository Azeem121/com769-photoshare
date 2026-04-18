# Architecture Notes — PhotoShare (COM769)

## Overview

This is a serverless, cloud-native photo-sharing application deployed entirely on Azure free-tier services.

## Component Map

```
Browser
  │
  ├─► Azure CDN (edge cache, HTTPS)
  │     └─► Azure Static Web Apps (frontend HTML/CSS/JS)
  │               └─► REST calls to Azure Functions
  │
  └─► Azure Functions (Python 3.11, consumption plan)
        ├─► Azure Cosmos DB (user/post/comment/rating data)
        └─► Azure Blob Storage (raw photo files)
```

## Design Decisions

### Serverless Functions (consumption plan)
- Zero cost at rest — billed only per invocation
- Auto-scales to demand without configuration
- Free tier: 1M invocations + 400K GB-s/month

### Cosmos DB (serverless + free tier)
- Serverless capacity mode removes the 400 RU/s minimum baseline cost
- Free tier grants 1000 RU/s and 25 GB — sufficient for a demo
- Session consistency balances cost and correctness for this workload

### Partition Key Strategy
| Container | Partition Key | Rationale |
|-----------|--------------|-----------|
| users     | /email       | Login lookups are always by email |
| posts     | /creatorId   | Creator feeds load all posts by a user |
| comments  | /postId      | Comments are always fetched per photo |
| ratings   | /postId      | Same as comments |

### JWT Authentication
- Stateless JWTs issued at login; validated in every Function
- `role` claim (`creator` / `consumer`) enforces endpoint access
- No creator self-registration — admin creates creator accounts directly in Cosmos DB

### CDN Caching
- Static assets (JS, CSS, images) cached at edge for 7 days
- API calls bypass CDN (dynamic routes)
- Reduces Static Web Apps bandwidth and improves perceived load time

### Blob Storage
- `photos` container set to public blob access
- Photos served directly from CDN-fronted blob URLs (no API proxy needed)
- Reduces Function invocations for image delivery

## Data Model

### users document
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "passwordHash": "bcrypt-hash",
  "name": "Display Name",
  "role": "creator | consumer",
  "createdAt": "ISO-8601"
}
```

### posts document
```json
{
  "id": "uuid",
  "creatorId": "user-uuid",
  "creatorName": "Display Name",
  "title": "string",
  "caption": "string",
  "location": "string",
  "people": ["name1", "name2"],
  "imageUrl": "https://blob.../photos/uuid.jpg",
  "avgRating": 4.2,
  "ratingCount": 17,
  "createdAt": "ISO-8601"
}
```

### comments document
```json
{
  "id": "uuid",
  "postId": "post-uuid",
  "authorId": "user-uuid",
  "authorName": "Display Name",
  "text": "string",
  "createdAt": "ISO-8601"
}
```

### ratings document
```json
{
  "id": "userId_postId",
  "postId": "post-uuid",
  "userId": "user-uuid",
  "rating": 4,
  "createdAt": "ISO-8601"
}
```

## API Endpoints

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| POST | /api/users/register | None | Register consumer account |
| POST | /api/users/login | None | Login, returns JWT |
| POST | /api/photos | Creator JWT | Upload photo + metadata |
| GET | /api/photos | Any | List/search photos (paginated) |
| GET | /api/photos/{id} | Any | Get single photo detail |
| POST | /api/photos/{id}/comments | Consumer JWT | Add comment |
| GET | /api/photos/{id}/comments | Any | List comments |
| POST | /api/photos/{id}/ratings | Consumer JWT | Submit 1–5 star rating |

## Scalability

- CDN absorbs read traffic for static content and photo files
- Cosmos DB serverless scales RU/s automatically with load
- Functions scale out horizontally up to 200 instances
- Blob Storage scales to petabytes without configuration
