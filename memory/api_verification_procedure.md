---
name: api_verification_procedure
description: Read-only verification procedure for circular attachment API endpoints
metadata:
  type: project
---

# API Endpoint Verification Procedure

## Route Summary (Read-Only)

| Endpoint | Method | Handler | Auth Dependency |
|---|---|---|---|
| `GET /files/{file_id}` | GET | `get_file()` | `get_current_user` |
| `GET /files/{file_id}/download` | GET | `download_file()` | `get_current_user_flexible` |
| `GET /files/{file_id}/preview` | GET | `preview_file()` | `get_current_user_flexible` |

## Authentication Flow

- **OAuth2 scheme**: `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")`
- **Required token**: `get_current_user` — extracts JWT from `Authorization: Bearer <token>` header
- **Flexible token**: `get_current_user_flexible` — token from `Authorization` header **or** query param `?token=<jwt>`
- **Login endpoint**: `POST /auth/login` with email/password → returns Bearer JWT
- **Token format**: Standard JWT with payload `{id, email, role.value}`

## Expected Response Status Codes

| Code | Category | Cause |
|---|---|---|
| **200** | Success | File found, authorization granted |
| **401** | Auth failure | Missing/invalid JWT token, expired token, or token parse failure |
| **403** | AuthZ failure | `check_file_permission()` returned False (deny-by-default: circular mismatch, missing profile/dept, wrong department) |
| **404** | Not found | File record does not exist in database |
| **5xx** | Server error | MinIO/storage read error, unexpected internal exception |

### Discriminating the Four Scenarios

| Situation | Expected HTTP Path |
|---|---|
| **401 authentication failure** | No `Authorization` header, malformed `Bearer` token, or invalid JWT signature → `{"detail": "Invalid authentication credentials"}` with `WWW-Authenticate: Bearer` header |
| **403 authorization failure** | Valid token, file exists, but `check_file_permission()` denies access → `{"detail": "Access denied. File belongs to another department."}` |
| **404 missing file** | Valid token, but `file_service.get_file(db, file_id)` returns None → `{"detail": "File not found"}` |
| **5xx server/storage failure** | Valid token, file exists, but MinIO read error → HTTP 500 or 404 with `detail: "File content could not be retrieved from storage"` |

## Minimum Test Data Required

To test an **authorized student**:
- A `User` record with `role = "student"` and active `is_active`
- Associated `StudentProfile` with `branch` set (e.g., `"CSE"`, `"AIML"`)
- A `File` record with `file_type = "circular"` and valid lecturer profile
- Lecturer `User` record with matching `department` (or compatible branch code)

To test an **unauthorized student**:
- Same as above but with **different department** branch/dept combination
- Or student with `branch = None` and `department = None`
- Or lecturer with `lecturer_profile = None` or `department = None`

## PowerShell Verification Commands (Read-Only, Do Not Execute)

### 1. GET /files/{file_id}

```powershell
# Replace with actual base URL and file ID
$baseUrl = "https://<your-api-host>"
$fileId = "<uuid-file-id>"
$token = "<jwt-token-supplied-at-runtime>"

# Using flexible auth (token from query param)
Invoke-Method -Method Get -Uri "$baseUrl/api/files/$fileId?token=$token" -Headers @{"Accept"="application/json"}

# OR using standard auth header
Invoke-WebRequest -Method Get -Uri "$baseUrl/api/files/$fileId" -Headers @{
    "Authorization" = "Bearer $token"
    "Accept" = "application/json"
}
# Examine $_.StatusCode, $_.Content, and response headers
```

### 2. GET /files/{file_id}/download

```powershell
$baseUrl = "https://<your-api-host>"
$fileId = "<uuid-file-id>"
$token = "<jwt-token-supplied-at-runtime>"

# Flexible auth with query param
Invoke-WebRequest -Method Get -Uri "$baseUrl/api/files/$fileId/download?token=$token" -Headers @{"Accept"="application/octet-stream"} |
    Save-FileFileName "/tmp/download-preview.tmp"

# OR with auth header
Invoke-WebRequest -Method Get -Uri "$baseUrl/api/files/$fileId/download" -Headers @{
    "Authorization" = "Bearer $token"
    "Accept" = "application/octet-stream"
} | Save-Item -Path "/tmp/download-preview.tmp"
```

### 3. GET /files/{file_id}/preview

```powershell
$baseUrl = "https://<your-api-host>"
$fileId = "<uuid-file-id>"
$token = "<jwt-token-supplied-at-runtime>"

Invoke-WebRequest -Method Get -Uri "$baseUrl/api/files/$fileId/preview?token=$token" -Headers @{"Accept"="application/json"} |
    # For image/PDF/text: returns inline content
    # For other types: returns attachment response
```

## Response Header Inspection (Safe)

For a **successful download**, inspect these headers **without exposing content**:

```powershell
# After Save-Item above
$headers = Get-Content "/tmp/download-preview.tmp" -Encoding Byte | Select-Object -First 256
# Look for:
# - Content-Disposition: attachment; filename="..."   (download endpoint)
# - Content-Disposition: inline; filename="..."     (preview for image/PDF/text)
# - Content-Length: NNN                           (byte count)
# - Content-Type: application/pdf                 (or image/*, text/*)
# - ETag or x-amz-meta headers (MinIO object metadata)
```

**Never print or forward** the actual file content, signed URLs, or credential-containing data. Only inspect headers and status codes.

## Execution Checklist (Approval Required Before Live Testing)

- [ ] Confirm base API URL and port with project owner
- [ ] Obtain valid JWT token from login (`POST /auth/login`) at runtime — do not hardcode
- [ ] Identify a test file ID where `file.file_type == "circular"`
- [ ] Identify a student user with branch set and lecturer with matching department
- [ ] Identify a student user with mismatched department (for 403 test)
- [ ] Identify a student user with missing branch/dept (for 403 test)
- [ ] Verify OAuth2 flow: login → token → use token in `Authorization: Bearer` header or `?token=` query param
- [ ] Prepare `Invoke-WebRequest` or `Invoke-Method` commands as shown above
- [ ] Do NOT execute until all items above are confirmed and approval is given

**Do not execute any live requests yet.** Wait for explicit approval before running the commands above.