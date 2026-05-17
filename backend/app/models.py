from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeviceSource(str, Enum):
    simulator = "simulator"


class CalibrationMode(str, Enum):
    empty = "empty"
    occupied = "occupied"


class DeviceConnectRequest(BaseModel):
    source: DeviceSource = DeviceSource.simulator


class CalibrationRequest(BaseModel):
    mode: CalibrationMode


class ConfigPatchRequest(BaseModel):
    presence_variance_threshold: float | None = Field(default=None, ge=0)


class EventEnvelope(BaseModel):
    event: str
    timestamp: float
    payload: dict[str, Any]


class StatusResponse(BaseModel):
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
