# wifiwavesdetection

Realtime Wi-Fi wave based room presence detection + heartbeat estimation with a high-energy live UI.

## Architecture

- **Backend (`/backend`)**: FastAPI service for realtime wave processing, presence classification, heartbeat extraction, calibration, and streaming events.
- **Frontend (`/frontend`)**: React + Vite dashboard that visualizes raw/filtered waves, person detection state, heartbeat BPM, and device health.
- **Transport**:
  - REST for controls/status
  - WebSocket for live events

## Current hardware mode

This implementation ships with a **simulator source** (`source=simulator`) so the full pipeline and UI can run without external CSI hardware.

## Backend setup

```bash
cd /home/runner/work/wifiwavesdetection/wifiwavesdetection/backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000
```

### Backend API

- `POST /api/device/connect` body: `{ "source": "simulator" }`
- `POST /api/device/disconnect`
- `POST /api/calibration/start` body: `{ "mode": "empty" | "occupied" }`
- `POST /api/calibration/stop`
- `PATCH /api/config` body: `{ "presence_variance_threshold": 0.02 }`
- `GET /api/status`
- `GET /api/health`
- `WS /ws/stream`

### WebSocket event contracts

- `waves.raw`: `{ points: number[], sampleRateHz: number }`
- `waves.filtered`: `{ points: number[], sampleRateHz: number }`
- `presence.state`: `{ detected: boolean, confidence: number, variance: number, threshold: number }`
- `heartbeat.bpm`: `{ bpm: number, quality: number }`
- `device.health`: `{ connected: boolean, source: string, packetRateHz: number, droppedPackets: number }`

## Frontend setup

```bash
cd /home/runner/work/wifiwavesdetection/wifiwavesdetection/frontend
npm install
npm run dev
```

Optional env:

```bash
VITE_API_BASE=http://localhost:8000
```

## Calibration runbook

1. Start stream in UI (`Start Stream`).
2. Keep room empty, click `Calibrate Empty` for a few seconds.
3. Stand in room, click `Calibrate Occupied` for a few seconds.
4. Click `Finish Calibration` to persist profiles and auto-update threshold.

## Testing

Backend:

```bash
cd /home/runner/work/wifiwavesdetection/wifiwavesdetection/backend
python -m pytest
```

Frontend:

```bash
cd /home/runner/work/wifiwavesdetection/wifiwavesdetection/frontend
npm run build
```

## Notes

- Heartbeat estimation uses spectral peak detection in a configurable BPM band.
- Presence uses variance + debounce to reduce false toggles.
- `backend/data/sample_wave.csv` is provided as starter replay data for future offline ingest tests.
