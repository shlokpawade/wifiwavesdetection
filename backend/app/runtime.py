import asyncio
import math
import random
import time
from collections import deque
from dataclasses import dataclass

import numpy as np
from fastapi import WebSocket

from app.config import AppConfig
from app.detection import PresenceDetector
from app.models import CalibrationMode
from app.signal import estimate_heartbeat_bpm, high_pass, moving_average


@dataclass
class RuntimeSnapshot:
    connected: bool
    source: str | None
    presence_detected: bool
    presence_confidence: float
    heartbeat_bpm: float | None
    heartbeat_quality: float
    presence_variance_threshold: float
    calibration_mode: str | None
    profiles: dict[str, float]
    packet_rate_hz: float
    dropped_packets: int


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        if not self._connections:
            return
        stale: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


class WiFiRuntime:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.manager = ConnectionManager()

        max_samples = max(60, config.sample_rate_hz * config.window_seconds)
        self._raw = deque(maxlen=max_samples)
        self._filtered = deque(maxlen=max_samples)
        self._raw_preview = deque(maxlen=config.waves_history_samples)
        self._filtered_preview = deque(maxlen=config.waves_history_samples)

        self._detector = PresenceDetector(config.presence_variance_threshold, config.presence_debounce_samples)
        self._connected = False
        self._source: str | None = None
        self._loop_task: asyncio.Task | None = None

        self._heartbeat_bpm: float | None = None
        self._heartbeat_quality = 0.0
        self._presence_confidence = 0.0
        self._packet_rate_hz = 0.0
        self._dropped_packets = 0

        self._calibration_mode: CalibrationMode | None = None
        self._calibration_variances: list[float] = []
        self._profiles: dict[str, float] = {}

        self._last_presence_emit_at = 0.0
        self._last_health_emit_at = 0.0

    @property
    def connected(self) -> bool:
        return self._connected

    def snapshot(self) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            connected=self._connected,
            source=self._source,
            presence_detected=self._detector.occupied,
            presence_confidence=self._presence_confidence,
            heartbeat_bpm=self._heartbeat_bpm,
            heartbeat_quality=self._heartbeat_quality,
            presence_variance_threshold=self._detector.threshold,
            calibration_mode=self._calibration_mode.value if self._calibration_mode else None,
            profiles=self._profiles,
            packet_rate_hz=self._packet_rate_hz,
            dropped_packets=self._dropped_packets,
        )

    async def connect_device(self, source: str) -> None:
        if self._connected:
            return
        self._connected = True
        self._source = source
        self._loop_task = asyncio.create_task(self._run())

    async def disconnect_device(self) -> None:
        self._connected = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

    def start_calibration(self, mode: CalibrationMode) -> None:
        self._calibration_mode = mode
        self._calibration_variances = []

    def stop_calibration(self) -> dict[str, float]:
        if not self._calibration_mode:
            return self._profiles

        if self._calibration_variances:
            self._profiles[self._calibration_mode.value] = float(np.mean(self._calibration_variances))

        self._calibration_mode = None
        self._calibration_variances = []

        if "empty" in self._profiles and "occupied" in self._profiles:
            updated_threshold = max(1e-6, (self._profiles["empty"] + self._profiles["occupied"]) / 2.0)
            self._detector.threshold = updated_threshold

        return self._profiles

    def patch_threshold(self, threshold: float) -> None:
        self._detector.threshold = max(1e-9, threshold)

    async def _emit(self, event: str, payload: dict) -> None:
        await self.manager.broadcast({"event": event, "timestamp": time.time(), "payload": payload})

    def _generate_sample(self, t: float, occupied_hint: bool) -> float:
        baseline = 0.15 * math.sin(2 * math.pi * 0.22 * t)
        noise = random.uniform(-0.03, 0.03)
        if occupied_hint:
            movement = 0.14 * math.sin(2 * math.pi * 0.9 * t)
            heartbeat = 0.03 * math.sin(2 * math.pi * 1.17 * t)
            return baseline + movement + heartbeat + noise
        return baseline + noise

    async def _run(self) -> None:
        period = 1.0 / self.config.sample_rate_hz
        emit_every_n = max(1, self.config.sample_rate_hz // self.config.ws_emit_hz)
        sample_counter = 0
        start_ts = time.monotonic()
        occupancy_flip_at = start_ts + 8.0
        occupied_hint = False

        while self._connected:
            tick_start = time.monotonic()
            now = time.time()
            monotonic_now = time.monotonic()

            if monotonic_now >= occupancy_flip_at:
                occupied_hint = not occupied_hint
                occupancy_flip_at = monotonic_now + random.uniform(8.0, 14.0)

            raw_value = self._generate_sample(monotonic_now, occupied_hint)
            self._raw.append(raw_value)
            self._raw_preview.append(raw_value)

            raw_arr = np.array(self._raw, dtype=float)
            smoothed = moving_average(raw_arr, window=5)
            filtered_arr = high_pass(smoothed, trend_window=15)
            filtered_value = float(filtered_arr[-1])

            self._filtered.append(filtered_value)
            self._filtered_preview.append(filtered_value)

            recent_window = np.array(list(self._filtered)[-max(20, self.config.sample_rate_hz * 3) :], dtype=float)
            variance = float(np.var(recent_window)) if recent_window.size else 0.0
            motion = float(np.mean(np.abs(np.diff(recent_window)))) if recent_window.size > 1 else 0.0
            presence_metric = variance + (0.6 * motion)
            presence = self._detector.update(presence_metric)
            self._presence_confidence = presence.confidence

            if self._calibration_mode:
                self._calibration_variances.append(presence_metric)

            heartbeat_bpm, heartbeat_quality = estimate_heartbeat_bpm(
                np.array(self._filtered, dtype=float),
                self.config.sample_rate_hz,
                self.config.heartbeat_low_bpm,
                self.config.heartbeat_high_bpm,
            )
            self._heartbeat_bpm = heartbeat_bpm
            self._heartbeat_quality = heartbeat_quality

            sample_counter += 1
            elapsed = max(0.001, monotonic_now - start_ts)
            self._packet_rate_hz = sample_counter / elapsed

            if sample_counter % emit_every_n == 0:
                await self._emit(
                    "waves.raw",
                    {
                        "points": list(self._raw_preview),
                        "sampleRateHz": self.config.sample_rate_hz,
                    },
                )
                await self._emit(
                    "waves.filtered",
                    {
                        "points": list(self._filtered_preview),
                        "sampleRateHz": self.config.sample_rate_hz,
                    },
                )

            if presence.changed or (now - self._last_presence_emit_at) > 1.0:
                self._last_presence_emit_at = now
                await self._emit(
                    "presence.state",
                    {
                        "detected": presence.occupied,
                        "confidence": presence.confidence,
                        "variance": presence_metric,
                        "threshold": self._detector.threshold,
                    },
                )

            if heartbeat_bpm is not None:
                await self._emit(
                    "heartbeat.bpm",
                    {
                        "bpm": round(float(heartbeat_bpm), 1),
                        "quality": round(float(heartbeat_quality), 3),
                    },
                )

            if (now - self._last_health_emit_at) > 1.0:
                self._last_health_emit_at = now
                await self._emit(
                    "device.health",
                    {
                        "connected": self._connected,
                        "source": self._source,
                        "packetRateHz": round(self._packet_rate_hz, 2),
                        "droppedPackets": self._dropped_packets,
                    },
                )

            sleep_time = max(0.0, period - (time.monotonic() - tick_start))
            await asyncio.sleep(sleep_time)
