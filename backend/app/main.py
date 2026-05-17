from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_config
from app.models import (
    CalibrationRequest,
    ConfigPatchRequest,
    DeviceConnectRequest,
    StatusResponse,
)
from app.runtime import WiFiRuntime

config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = WiFiRuntime(config)
    yield
    await app.state.runtime.disconnect_device()


app = FastAPI(title="wifiwavesdetection", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.trusted_hosts_list or ["*"])


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/device/connect")
async def connect_device(payload: DeviceConnectRequest) -> StatusResponse:
    await app.state.runtime.connect_device(payload.source.value)
    return StatusResponse(**app.state.runtime.snapshot().__dict__)


@app.post("/api/device/disconnect")
async def disconnect_device() -> StatusResponse:
    await app.state.runtime.disconnect_device()
    return StatusResponse(**app.state.runtime.snapshot().__dict__)


@app.post("/api/calibration/start")
async def start_calibration(payload: CalibrationRequest) -> StatusResponse:
    app.state.runtime.start_calibration(payload.mode)
    return StatusResponse(**app.state.runtime.snapshot().__dict__)


@app.post("/api/calibration/stop")
async def stop_calibration() -> StatusResponse:
    app.state.runtime.stop_calibration()
    return StatusResponse(**app.state.runtime.snapshot().__dict__)


@app.patch("/api/config")
async def patch_config(payload: ConfigPatchRequest) -> StatusResponse:
    if payload.presence_variance_threshold is not None:
        app.state.runtime.patch_threshold(payload.presence_variance_threshold)
    return StatusResponse(**app.state.runtime.snapshot().__dict__)


@app.get("/api/status")
async def status() -> StatusResponse:
    return StatusResponse(**app.state.runtime.snapshot().__dict__)


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket) -> None:
    await app.state.runtime.manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        app.state.runtime.manager.disconnect(websocket)
    except Exception:
        app.state.runtime.manager.disconnect(websocket)
