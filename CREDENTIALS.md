# Keystone Portal — Demo Credentials

> **DO NOT commit this file to a public repository.**

## Admin Login

| Field    | Value              |
|----------|--------------------|
| Email    | `admin@keystone.io` |
| Password | `admin123`          |

## Seed Data

Run the seed endpoint after starting the stack:

```bash
curl -X POST http://localhost:8080/api/seed
```

This creates the admin user above along with 4 team accounts, 32 infrastructure requests, and 132 timeline events.
