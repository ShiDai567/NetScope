# Backend API Design

## Overview

This document defines the Django backend API for NetScope.

Goals:

- Preserve frontend compatibility for `GET /api/packet`
- Replace in-memory backend logic with Django services and database models
- Add a durable iKuai integration flow that can persist login sessions
- Keep responses JSON-based and simple for the existing frontend

Base URL during local development:

```text
http://localhost:4000
```

Content type:

```text
application/json
```

## Resource Summary

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/packet` | Return 1 to 3 simulated packets for frontend polling |
| GET | `/api/nodes` | List active network nodes |
| GET | `/api/routes` | List active allowed routes |
| POST | `/api/ikuai/login` | Log in to iKuai and persist a session record |
| GET | `/api/ikuai/sessions` | List recent iKuai login sessions |

## Common Response Rules

- Success responses use HTTP `200` unless otherwise noted
- Validation errors use HTTP `400`
- Authentication failure from iKuai uses HTTP `401`
- Upstream router/network failures use HTTP `502`
- Not found uses HTTP `404`

Error payload shape:

```json
{
  "error": "human readable message"
}
```

## 1. Health Check

### `GET /api/health`

Returns backend process status.

Response example:

```json
{
  "status": "ok",
  "service": "netscope-backend",
  "uptime": 123.456,
  "database": "ok",
  "time": "2026-04-24T18:00:00Z"
}
```

## 2. Simulated Packet Feed

### `GET /api/packet`

Returns 1 to 3 simulated packets. This response is intentionally compatible with the current frontend in `frontend/src/app/page.jsx`.

Query params:

- `count`: optional, integer, min `1`, max `10`

Response example:

```json
[
  {
    "id": "pkt_001",
    "source": {
      "ip": "192.168.1.10",
      "name": "Client (Beijing)",
      "lat": 39.9,
      "lng": 116.4,
      "type": "client"
    },
    "destination": {
      "ip": "8.8.8.8",
      "name": "Server (Silicon Valley)",
      "lat": 27.994110585072477,
      "lng": 120.69934126685061,
      "type": "server"
    },
    "protocol": "TCP",
    "status": "success",
    "payloadSize": 1024,
    "timestamp": 1712450000
  }
]
```

Generation rules:

- Source and destination must follow allowed routes from the database
- Only `server -> client`, `client -> server`, and `server -> server` are valid
- `protocol` must be one of `TCP`, `UDP`, `ICMP`
- `status` must be one of `success`, `delayed`, `dropped`
- Returned packets should also be recorded in the database for history and later expansion

## 3. Nodes

### `GET /api/nodes`

Lists all enabled network nodes used by packet generation.

Response example:

```json
[
  {
    "id": "srv_us",
    "name": "Server (Silicon Valley)",
    "ip": "8.8.8.8",
    "type": "server",
    "lat": 27.994110585072477,
    "lng": 120.69934126685061,
    "isActive": true
  }
]
```

## 4. Routes

### `GET /api/routes`

Lists active allowed routes between nodes.

Response example:

```json
[
  {
    "id": 1,
    "sourceNodeId": "srv_us",
    "destinationNodeId": "cli_cn",
    "isActive": true
  }
]
```

## 5. iKuai Login

### `POST /api/ikuai/login`

Logs in to an iKuai panel, captures returned cookies, and stores the session in the database.

Request body:

```json
{
  "routerUrl": "http://10.1.1.1",
  "username": "admin",
  "password": "123",
  "remember_password": ""
}
```

Field rules:

- `routerUrl`: required, absolute base URL to iKuai router
- `username`: required
- `password`: required, plaintext input from caller
- `remember_password`: optional, string, default `""`

Backend behavior:

1. Convert plaintext password to lowercase 32-character MD5
2. Generate a random 20-character `pass` field
3. Submit login request to `{routerUrl}/Action/login`
4. Prefer JSON request body and fallback to form-encoded body if needed
5. Extract `sess_key` from `Set-Cookie`
6. Persist request and response summary to database

Success response example:

```json
{
  "id": 12,
  "loginUrl": "http://10.1.1.1/Action/login",
  "requestMode": "json",
  "requestPayload": {
    "username": "admin",
    "passwd": "202cb962ac59075b964b07152d234b70",
    "pass": "ac59075b964b07150000",
    "remember_password": ""
  },
  "upstreamStatus": 200,
  "upstreamResponse": {
    "Result": 10000,
    "ErrMsg": "Succeess"
  },
  "cookies": {
    "sess_key": "0249f5edebd84e26103c1193a4ede2c8"
  },
  "sess_key": "0249f5edebd84e26103c1193a4ede2c8",
  "cookieHeader": "sess_key=0249f5edebd84e26103c1193a4ede2c8; username=admin; login=1",
  "createdAt": "2026-04-24T18:00:00Z"
}
```

Validation error example:

```json
{
  "error": "routerUrl, username, password are required"
}
```

Authentication failure example:

```json
{
  "id": 13,
  "loginUrl": "http://10.1.1.1/Action/login",
  "upstreamStatus": 200,
  "upstreamResponse": {
    "Result": 10001,
    "ErrMsg": "用户名或密码错误"
  },
  "sess_key": null
}
```

## 6. iKuai Session History

### `GET /api/ikuai/sessions`

Returns recent iKuai login attempts.

Query params:

- `limit`: optional, integer, default `20`, max `100`

Response example:

```json
[
  {
    "id": 12,
    "routerUrl": "http://10.1.1.1",
    "username": "admin",
    "requestMode": "json",
    "resultCode": 10000,
    "resultMessage": "Succeess",
    "sessKey": "0249f5edebd84e26103c1193a4ede2c8",
    "cookieHeader": "sess_key=0249f5edebd84e26103c1193a4ede2c8; username=admin; login=1",
    "createdAt": "2026-04-24T18:00:00Z"
  }
]
```

## Non-Goals For This Refactor

- No Django admin customization yet
- No authentication layer for NetScope API yet
- No packet filtering, pagination, or websocket streaming yet
- No router credential encryption-at-rest yet beyond not storing plaintext passwords
