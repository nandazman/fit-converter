# 🏊 Swim OCR App — Requirements

## Overview
A lightweight **FastAPI + Tesseract** service that extracts swimming segment data from **Huawei Health → Pool Swim → Segments** screenshots.

**Features**
- REST API to upload an image and return parsed **JSON** plus a downloadable **CSV**.
- Minimal static **UI** (HTML + vanilla JS) to upload and preview results.
- **Nginx** reverse proxy for `/swim` (UI) and `/api/*` (backend).
- Systemd service for the API process.
- GitHub Actions **CI/CD** to test and auto-deploy to your server via SSH.

---

## Functional Requirements

### OCR Extraction
- Accepts image uploads: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`.
- Preprocess image (grayscale, denoise, adaptive threshold, upscale) for better OCR.
- Use **Tesseract** via `pytesseract`.
- Extract per-lap fields:
  - `lap` (int)
  - `stroke_type` (string; e.g., Breaststroke, Freestyle)
  - `lap_length_m` (int; e.g., 50)
  - `duration_sec` (int; total seconds)
  - `strokes` (int)
  - `swolf` (int)
  - `pace_per_100m_sec` (int; seconds/100 m)

### API Endpoints
- `POST /api/ocr` → Multipart `file` upload. Returns:
  ```json
  {
    "date": "YYYY-MM-DD",
    "segments": [ { ... } ],
    "csv_url": "/api/ocr.csv?id=<uuid>"
  }
  ```
- `GET /api/ocr.csv?id=<uuid>` → Returns CSV for that OCR run.
- `GET /healthz` → `{ "ok": true }`

### UI
- Route: `/swim/` (single `index.html`).
- Upload image → call `/api/ocr` → show JSON and a **Download CSV** link.

---

## Non-Functional Requirements
- Runs on Ubuntu server (2 vCPU, 2 GB RAM, 40 GB disk).
- Tesseract installed via apt.
- FastAPI served by **uvicorn**, managed by **systemd**, proxied by **Nginx**.
- CI must run lint/tests on every push and **deploy on pushes to `main`**.

---

## Tech Stack
- **Backend**: Python 3.10+, FastAPI, Uvicorn
- **OCR**: Tesseract, pytesseract, OpenCV, Pillow
- **Frontend**: Static HTML + JS
- **Web**: Nginx reverse proxy
- **Process**: systemd
- **CI/CD**: GitHub Actions over SSH

---

## Folder Structure (target)
```
swim-ocr/
├─ app/
│  └─ main.py
├─ static/
│  └─ index.html
├─ requirements.txt
├─ REQUIREMENTS.md
├─ deploy.sh
└─ .github/workflows/deploy.yml
```

---

## Server Prerequisites (one-time)
```bash
sudo apt update
sudo apt install -y tesseract-ocr libtesseract-dev python3-venv nginx
sudo ufw allow 'Nginx Full' || true
```

Create a dedicated app directory the CI will sync to:
```bash
sudo mkdir -p /opt/swim-ocr
sudo chown -R $USER:$USER /opt/swim-ocr
```

Create the **systemd** unit (CI restarts it):
`/etc/systemd/system/swim-ocr.service`
```ini
[Unit]
Description=Swim OCR API
After=network.target

[Service]
User=%i
WorkingDirectory=/opt/swim-ocr
Environment="PATH=/opt/swim-ocr/.venv/bin"
ExecStart=/opt/swim-ocr/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
> Replace `%i` with your deploy user *OR* keep this file managed by CI via `deploy.sh`.

**Nginx** site (example):
```
server {
  listen 80;
  server_name YOUR_DOMAIN_OR_IP;

  location /swim/ {
    alias /opt/swim-ocr/static/;
    try_files $uri $uri/ /index.html;
  }

  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    client_max_body_size 20M;
  }

  location /healthz {
    proxy_pass http://127.0.0.1:8000/healthz;
  }
}
```
Enable:
```bash
sudo ln -s /etc/nginx/sites-available/swim-ocr.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## CI/CD (GitHub Actions)
- On push to `main`:
  1. Set up Python; install deps
  2. Run basic import test
  3. **Deploy** over SSH:
     - rsync repo to `/opt/swim-ocr`
     - create/upgrade Python venv
     - install `requirements.txt`
     - reload systemd service `swim-ocr`
- Required repository **Secrets**:
  - `DEPLOY_HOST` → server IP or domain (e.g., `129.226.213.101`)
  - `DEPLOY_USER` → SSH user (e.g., `ubuntu`)
  - `DEPLOY_SSH_KEY` → Private key (PEM) with access to the server
  - (optional) `SERVICE_NAME` → default `swim-ocr`

See `.github/workflows/deploy.yml` in this package.

---

## Example Response
```json
{
  "date": "2025-10-18",
  "segments": [
    {
      "lap": 1,
      "stroke_type": "Breaststroke",
      "lap_length_m": 50,
      "duration_sec": 148,
      "strokes": 37,
      "swolf": 185,
      "pace_per_100m_sec": 296
    }
  ],
  "csv_url": "/api/ocr.csv?id=abcd1234"
}
```
