import numpy as np

from app.signal import estimate_heartbeat_bpm


def test_estimate_heartbeat_bpm_detects_peak() -> None:
    sample_rate = 20
    seconds = 20
    time = np.linspace(0, seconds, sample_rate * seconds, endpoint=False)

    expected_bpm = 72
    hz = expected_bpm / 60.0
    signal = 0.6 * np.sin(2 * np.pi * hz * time)

    bpm, quality = estimate_heartbeat_bpm(signal, sample_rate_hz=sample_rate, low_bpm=48, high_bpm=132)

    assert bpm is not None
    assert abs(bpm - expected_bpm) < 3
    assert quality > 0.2
