# Backend Database Design

## Overview

The Django backend will use SQLite for local development.

Goals:

- Move hardcoded node and route definitions into persistent tables
- Persist generated packet events for history and future analytics
- Persist iKuai login sessions and upstream results
- Keep the schema small and easy to migrate

## Database Engine

- Local development: SQLite
- Default file: `backend/db.sqlite3`

## Entity Relationship Summary

```text
NetworkNode 1---* NetworkRoute (source)
NetworkNode 1---* NetworkRoute (destination)
NetworkNode 1---* PacketEvent (source)
NetworkNode 1---* PacketEvent (destination)
iKuaiSession 1---0..* future iKuai actions
```

## 1. `traffic_networknode`

Stores network visualization nodes.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | bigint | PK | Django default primary key |
| `node_id` | varchar(64) | unique, indexed | Stable external ID like `srv_us` |
| `name` | varchar(255) | required | Display name |
| `ip_address` | generic IP field | required, indexed | IPv4/IPv6 ready |
| `node_type` | varchar(16) | indexed | `server` or `client` |
| `latitude` | decimal(9,6) | required | Map coordinate |
| `longitude` | decimal(9,6) | required | Map coordinate |
| `is_active` | bool | default true | Controls whether node is used |
| `created_at` | datetime | auto | |
| `updated_at` | datetime | auto | |

Rules:

- `node_type` allowed values: `server`, `client`
- inactive nodes are excluded from packet generation

## 2. `traffic_networkroute`

Stores allowed traffic routes.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | bigint | PK | |
| `source_node_id` | FK -> `traffic_networknode` | indexed | |
| `destination_node_id` | FK -> `traffic_networknode` | indexed | |
| `is_active` | bool | default true | |
| `created_at` | datetime | auto | |
| `updated_at` | datetime | auto | |

Constraints:

- unique pair on `(source_node_id, destination_node_id)`
- prevent self-route
- allow only:
  - `server -> client`
  - `client -> server`
  - `server -> server`
- disallow `client -> client`

## 3. `traffic_packetevent`

Stores simulated packets returned by the feed.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | bigint | PK | |
| `packet_id` | varchar(64) | unique, indexed | External ID like `pkt_001` |
| `source_node_id` | FK -> `traffic_networknode` | indexed | |
| `destination_node_id` | FK -> `traffic_networknode` | indexed | |
| `protocol` | varchar(16) | indexed | `TCP`, `UDP`, `ICMP` |
| `status` | varchar(16) | indexed | `success`, `delayed`, `dropped` |
| `payload_size` | positive integer | required | bytes |
| `event_timestamp` | datetime | indexed | Packet event time |
| `created_at` | datetime | auto | Row creation time |

Indexes:

- `(event_timestamp, status)`
- `(source_node_id, destination_node_id, event_timestamp)`

Notes:

- Current frontend only reads live responses, but persistence enables history, replay, and analytics later

## 4. `integrations_ikuaisession`

Stores iKuai login attempts and resulting session data.

| Column | Type | Constraints | Notes |
| --- | --- | --- | --- |
| `id` | bigint | PK | |
| `router_url` | URL/text | indexed | Base router URL |
| `login_url` | URL/text | required | Usually `{router_url}/Action/login` |
| `username` | varchar(255) | indexed | |
| `request_mode` | varchar(16) | required | `json` or `form` |
| `request_payload` | JSON | required | Sanitized payload without plaintext password |
| `upstream_status` | positive integer | null allowed | HTTP status from router |
| `result_code` | positive integer | null allowed | iKuai `Result` |
| `result_message` | varchar(255) | blank allowed | iKuai `ErrMsg` |
| `cookies` | JSON | required | Parsed cookies |
| `sess_key` | varchar(255) | blank allowed, indexed | Session cookie value |
| `cookie_header` | text | blank allowed | Ready-to-use cookie header |
| `response_headers` | JSON | required | Upstream headers snapshot |
| `upstream_response` | JSON | required | Raw upstream response body |
| `created_at` | datetime | auto | |

Security notes:

- Do not store plaintext password
- Store only hashed `passwd` field that was sent upstream
- Cookies are intentionally stored because session reuse is a product requirement

## Seed Data

Initial migration or bootstrap command should create:

- `srv_us` server
- `cli_cn` client
- `cli_eu` client
- `cli_br` client
- routes for:
  - every server -> client
  - every client -> server
  - every server -> server pair

## Service Layer Responsibilities

### Packet generation service

- load active routes
- randomly choose route
- randomly choose protocol and status
- generate payload size
- persist packet event
- return frontend-compatible payload

### iKuai session service

- validate input
- compute MD5 password
- call upstream login API
- parse cookies
- persist session
- return API response payload

## Future Migration Ideas

- Add `TrafficSnapshot` for aggregated metrics
- Add `IKuaiCommandLog` for authenticated downstream operations
- Add soft-delete or audit trail tables
- Move SQLite to PostgreSQL when multi-user concurrency becomes important
