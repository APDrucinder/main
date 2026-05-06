# Backend API Contract (Frontend Integration)

Base URL: `http://127.0.0.1:8000`

All success responses:

```json
{ "data": ... }
```

All error responses:

```json
{ "error": { "code": "...", "message": "..." } }
```

## Auth

### `POST /auth/login`
Request:

```json
{
  "email": "user@example.com",
  "password": "string"
}
```

Success:

```json
{
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "subscription_tier": "free"
    }
  }
}
```

Side effect: sets `HttpOnly` session cookie.

### `POST /auth/logout`
Success:

```json
{ "data": { "logged_out": true } }
```

Side effect: clears session cookie.

### `GET /auth/me`
Success:

```json
{
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "subscription_tier": "free"
    }
  }
}
```

## Dashboard

### `GET /dashboard`
Success:

```json
{
  "data": {
    "stats": {
      "total_applied": 0,
      "applied_today": 0,
      "applied_this_week": 0,
      "interviews": 0
    },
    "recent_applications": [
      {
        "application_id": "uuid",
        "status": "matched",
        "match_score": 80,
        "applied_at": "ISO-8601",
        "job": {
          "id": "uuid",
          "title": "string",
          "company": "string",
          "location": "string",
          "apply_url": "string"
        }
      }
    ]
  }
}
```

## Applications

### `GET /applications`
Success:

```json
{
  "data": {
    "applications": [
      {
        "application_id": "uuid",
        "status": "matched",
        "match_score": 80,
        "matched_skills": ["python"],
        "missing_skills": ["aws"],
        "reasoning": "string",
        "manual_apply_url": "string|null",
        "applied_at": "ISO-8601",
        "job": {
          "id": "uuid",
          "title": "string",
          "company": "string",
          "location": "string",
          "salary_range": "string|null",
          "apply_url": "string",
          "source": "string|null"
        }
      }
    ],
    "total": 1
  }
}
```

## Settings

### `PATCH /settings`
Request:

```json
{
  "target_roles": ["backend engineer"],
  "locations": ["Bangalore"],
  "experience_years": 2,
  "salary_min": 1200000,
  "remote_ok": true,
  "auto_apply_threshold": 75
}
```

Success:

```json
{ "data": { "settings": { "...": "..." } } }
```

## Onboarding

### `POST /onboarding`
Request:

```json
{
  "full_name": "User Name",
  "target_roles": ["backend engineer"],
  "locations": ["Bangalore"],
  "experience_years": 2,
  "salary_min": 1200000,
  "remote_ok": true,
  "auto_apply_threshold": 75
}
```

Success:

```json
{
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "subscription_tier": "free"
    },
    "onboarding_completed": true,
    "settings": {
      "target_roles": ["backend engineer"],
      "locations": ["Bangalore"],
      "experience_years": 2,
      "salary_min": 1200000,
      "remote_ok": true,
      "auto_apply_threshold": 75
    }
  }
}
```
