# Melodyxx — Agent Guidelines & Instructions (AGENTS.md)

Welcome to the **Melodyxx** codebase. This document outlines critical rules, architecture principles, and development workflows for all AI coding assistants and developers collaborating on this project.

---

## 1. Project Philosophy & Core Architecture

1. **Zero-Disk Streaming (Cobalt-Style Pipeline)**:
   - **NEVER** save downloaded audio files, video files, or intermediate transcoding buffers to disk.
   - All conversions (FFmpeg) MUST be piped on-the-fly (`stdout -> client response`).
   - Disk usage for audio operations must remain strictly **0 MB**.
2. **Apple Music Metadata & High-Resolution Artwork**:
   - Audio metadata (Artist, Title, Album, Release Year, High-Res 800x800 Artwork) is resolved automatically via `metadata_resolver.py`.
   - FFmpeg dual-input pipes embed official artwork directly into ID3v2.3 MP3 tags on-the-fly.
3. **Resilient Streaming & Auto-Fallback**:
   - Before committing `HTTP 200` headers to the client, the backend must verify the initial audio chunk from FFmpeg.
   - If dual-input (audio + poster) encounters network issues or timeout from cover art CDNs, the pipeline must **automatically fall back to audio-only stream** to ensure 100% playable files and prevent corrupt 0 KB downloads.
4. **Language & Localization**:
   - The entire Web UI (HTML, CSS, JavaScript, user-facing notifications, placeholders, and error messages) must remain strictly in **English**.
   - User conversations in chat are conducted in **Indonesian** (unless explicitly asked otherwise).

---

## 2. Automatic Semantic Versioning Protocol (CRITICAL)

The project follows strict **Semantic Versioning 2.0.0** (`MAJOR.MINOR.PATCH`).
The file [`VERSION`](./VERSION) at the repository root is the **Single Source of Truth** for the application version (e.g. `1.0.0`).

### 📌 Agent Rule: Automatic Version Bump on Every Change
Whenever an AI agent makes code modifications or completes a task, the agent **MUST evaluate the scope of changes and automatically bump the version in `VERSION`**:

| Release Type | Version Bump | Trigger Criteria |
| :--- | :--- | :--- |
| **MAJOR** | `X.0.0` $\rightarrow$ `(X+1).0.0` | Breaking changes, core streaming architecture redesigns, major breaking API changes, or complete redesigns of the user interface. |
| **MINOR** | `X.Y.0` $\rightarrow$ `X.(Y+1).0` | New user-facing features, new capabilities (e.g., adding discography browser, batch download queue, quality selector, playlist import), or non-breaking API additions. |
| **PATCH** | `X.Y.Z` $\rightarrow$ `X.Y.(Z+1)` | Bug fixes, edge-case fixes (e.g. 0 KB corrupt file fix, auto-jump fix, rate-limit adjustments), performance improvements, CSS alignment, or documentation updates. |

### 🔄 Required Version Sync Steps for Agents:
Whenever you bump the version in `VERSION` (e.g., from `1.0.0` to `1.0.1`):
1. **Update `VERSION`**:
   Write the new SemVer string into [`VERSION`](./VERSION) (e.g. `1.0.1`).
2. **Update Cache-Busters in `static/index.html`**:
   Update CSS and JS version queries to match the new version:
   ```html
   <link rel="stylesheet" href="/static/css/style.css?v=1.0.1" />
   <script src="/static/js/app.js?v=1.0.1" defer></script>
   ```
3. **Bump Service Worker Cache Name in `static/sw.js`**:
   Increment cache name to force client browsers to bust old cache (e.g. `melodyxx-v21`).
4. **Git Commit Message**:
   Include the new version tag in the commit message:
   ```bash
   git commit -m "fix(stream): prevent 0kb files and bump version to v1.0.1"
   ```

---

## 3. Key Endpoints

- `GET /` — Serves the frontend single-page application (`static/index.html`).
- `GET /api/version` — Returns dynamic JSON `{ version: "v1.0.0", commit: "fa792a8", version_url: "...", commit_url: "..." }`.
- `GET /api/health` — System status, active streams, and version health check.
- `GET /api/search` — Fast YouTube audio search.
- `GET /api/artist/search` — Apple Music artist search.
- `GET /api/artist/{id}/discography` — Discography, top popular tracks, and album tracks.
- `POST /api/download` — Stream URL pre-validation, metadata resolution & token issuance.
- `GET /api/stream` — Zero-disk direct stream piping to browser or download manager.

---

## 4. UI Standards

- The version badge in the footer displays the current version dynamically (`v1.0.0`), fetched via `/api/version`.
- Artist search must **never auto-jump** into discography without user selection; always render the matching artist cards first.
- In batch downloads, successful downloads are automatically deselected; failed tracks remain selected and the drawer displays a **Retry Failed Tracks** button.
- **In-App Auto-Update Notification**: When a new version is detected (via Service Worker or periodic polling), a floating top banner `#update-notification-banner` prompts the user to refresh with one click (`btn-update-reload`).

