# 08 — Security and privacy

## 1. Threat model (summary)

| Threat | Control | Residual risk |
| --- | --- | --- |
| Credential theft | bcrypt (cost 12), 30-min access token, 7-day rotating refresh, revocation on logout | Phishing; no MFA in this build |
| Token replay | Refresh tokens stored hashed, rotated on use, session row tracks jti/IP/UA | Stolen access token valid until expiry |
| Tenant escape | `org_filter` on every query + `ensure_org_access` on loaded rows | A new router that forgets both; tests cover the pattern |
| Privilege escalation | `can_assign_role` prevents granting a role above your own; super admin cannot be created inside an org | Compromised org admin can over-grant within their tenant |
| Brute force | Rate limit per IP on `/auth/login`, generic 401 message | Distributed attack from many IPs |
| Data breach at rest | Fernet encryption for phone, licence, emergency contact; masked responses | VIN and email are plaintext |
| Secret leakage | All provider keys server-side; frontend bundle contains no secrets | `.env` committed by accident (`.gitignore` blocks it) |
| Injection | SQLAlchemy parameter binding everywhere; no raw SQL string interpolation | JSON stored and re-serialised, never executed |
| Report misuse | Downloads authenticated, reports carry provenance footer | A authorised user can still export data |
| Abuse of "AI says" | Disclaimers in API, UI, PDF; assistant refuses medical/legal/prediction | Users may over-trust a score anyway |

## 2. RBAC matrix

Permissions are strings `resource:action`. Grants are stored in `role_permissions` and seeded from
`core/rbac.py`.

| Permission | Super | Org admin | Fleet mgr | Safety officer | Driver |
| --- | --- | --- | --- | --- | --- |
| `dashboard:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `vehicles:read` | ✓ | ✓ | ✓ | ✓ | — |
| `vehicles:create/update` | ✓ | ✓ | ✓ | — | — |
| `vehicles:delete` | ✓ | ✓ | — | — | — |
| `drivers:read` | ✓ | ✓ | ✓ | ✓ | — |
| `drivers:create/update/delete` | ✓ | ✓ | — | — | — |
| `tracking:read` | ✓ | ✓ | ✓ | ✓ | — |
| `tracking:manage` (geofences) | ✓ | ✓ | ✓ | — | — |
| `behaviour:read` | ✓ | ✓ | ✓ | ✓ | — |
| `behaviour:configure` | ✓ | ✓ | — | — | — |
| `scores:read` | ✓ | ✓ | ✓ | ✓ | own only |
| `scores:configure` | ✓ | ✓ | — | — | — |
| `risk:read` | ✓ | ✓ | ✓ | ✓ | — |
| `risk:assess` | ✓ | ✓ | ✓ | ✓ | — |
| `incidents:read` | ✓ | ✓ | ✓ | ✓ | — |
| `incidents:create` | ✓ | ✓ | ✓ | ✓ | — |
| `incidents:manage` | ✓ | ✓ | ✓ | ✓ | — |
| `maintenance:read` | ✓ | ✓ | ✓ | ✓ | — |
| `maintenance:manage` | ✓ | ✓ | ✓ | — | — |
| `reports:read/generate` | ✓ | ✓ | ✓ | ✓ | — |
| `notifications:read` | ✓ | ✓ | ✓ | ✓ | own |
| `notifications:manage` | ✓ | ✓ | — | — | own prefs |
| `assistant:use` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `road_safety:read` | ✓ | ✓ | ✓ | ✓ | — |
| `road_safety:report` | ✓ | ✓ | ✓ | ✓ | — |
| `team:read` | ✓ | ✓ | ✓ | — | — |
| `team:manage` | ✓ | ✓ | — | — | — |
| `settings:read` | ✓ | ✓ | — | — | — |
| `settings:manage` | ✓ | ✓ | — | — | — |
| `billing:read` | ✓ | ✓ | — | — | — |
| `billing:manage` | ✓ | ✓ | — | — | — |
| `audit:read` | ✓ | ✓ | — | — | — |
| `ai_models:read/manage` | ✓ | — | — | — | — |
| `organisations:manage` | ✓ | — | — | — | — |
| `subscriptions:manage` | ✓ | — | — | — | — |

Driver visibility is scoped in the handler: drivers can read their own scores and notifications but never
list other drivers.

## 3. Password and token handling

- Passwords: bcrypt with 12 rounds, 72-byte truncation handled by passlib.
- Access token: HS256, `sub`, `role`, `org`, `jti`, `exp` (30 min).
- Refresh token: opaque, 7 days, stored as SHA-256 in `refresh_tokens`; rotation on every refresh.
- Logout: revokes the session's refresh token; the presented access token expires naturally.
- `change-password` requires the current password and does not invalidate other sessions automatically
  (documented residual risk).

## 4. Transport and headers

- nginx terminates TLS; HSTS should be enabled at the edge for production.
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy` set in nginx.
- CORS allow-list comes from `CORS_ORIGINS`; credentials are allowed only for listed origins.
- `Content-Disposition` is exposed so the frontend can name downloaded reports.

## 5. Privacy principles

| Principle | Implementation |
| --- | --- |
| Lawful basis and transparency | Monitoring-policy acceptance recorded on the organisation (`monitoring_policy_accepted_at`); the register page requires an explicit acknowledgement |
| Data minimisation | Only fields needed for safety operations are collected; emergency contacts are optional and encrypted |
| Purpose limitation | Data is used for coaching, maintenance and reporting — not for insurance scoring or advertising |
| Retention | `DATA_RETENTION_DAYS` (default 365) governs pruning of locations and events |
| Access control | Role + tenant scoping; PII masked in list views, decrypted only for detail views where necessary |
| Security of processing | Encryption at rest for PII, bcrypt for passwords, hashed device keys |
| Subject access | A driver can see their own scores and events; export via reporting |
| Erasure | Soft delete for drivers/vehicles preserves audit integrity; hard delete cascades where policy requires it |

### Camera and distraction data

Distraction events are only created from camera payloads that arrive through an authorised integration.
They are stored with `confidence` and never presented as a confirmed violation. In this build no camera
integration is enabled, so no distraction events are produced.

## 6. Audit logging

Every write path calls `log_action(db, user=..., action="...", resource_type=..., resource_id=..., detail=..., request=...)`.
Entries capture actor, action, resource, structured detail, IP and user agent. Reads are not logged
(except report downloads, which are logged at generation).

Audited actions include: `auth.login`, `vehicle.create/update/archive`, `driver.create/update`,
`incident.create/investigate/verify/resolve/false_alert/note`, `report.generate`, `score.config.update`,
`team.member.create/update`, `subscription.upgrade/cancel`, `maintenance.record.create`.

## 7. Known gaps (do not assume these exist)

- **No MFA / SSO / SAML.** Listed on the Enterprise plan as roadmap, not implemented.
- **No IP allow-listing or device binding for sessions.**
- **No field-level encryption for VIN or email** (masked in responses only).
- **No automated penetration test** has been performed.
- **No WAF** in the provided nginx configuration.
- Rate limiting is in-process by default; multi-instance deployments need Redis.

These are stated in [18 — Limitations](18-limitations-and-honesty.md) as well, because claiming otherwise
would be dishonest.
