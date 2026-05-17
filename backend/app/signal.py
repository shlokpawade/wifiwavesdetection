import numpy as np


def moving_average(values: np.ndarray, window: int = 5) -> np.ndarray:
    if window <= 1 or values.size <= 1:
        return values
    window = min(window, values.size)
    kernel = np.ones(window) / window
    return np.convolve(values, kernel, mode="same")


def high_pass(values: np.ndarray, trend_window: int = 15) -> np.ndarray:
    if values.size <= 2:
        return values
    trend = moving_average(values, window=max(3, trend_window))
    return values - trend


def estimate_heartbeat_bpm(
    values: np.ndarray,
    sample_rate_hz: int,
    low_bpm: int,
    high_bpm: int,
) -> tuple[float | None, float]:
    if sample_rate_hz <= 0:
        return None, 0.0
    min_samples = sample_rate_hz * 6
    if values.size < min_samples:
        return None, 0.0

    centered = values - np.mean(values)
    if np.allclose(centered, 0):
        return None, 0.0

    n = centered.size
    windowed = centered * np.hanning(n)
    fft = np.fft.rfft(windowed)
    power = np.abs(fft) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)

    low_hz = low_bpm / 60.0
    high_hz = high_bpm / 60.0

    band_mask = (freqs >= low_hz) & (freqs <= high_hz)
    if not np.any(band_mask):
        return None, 0.0

    band_power = power[band_mask]
    band_freqs = freqs[band_mask]
    peak_idx = int(np.argmax(band_power))

    peak_power = float(band_power[peak_idx])
    total_band_power = float(np.sum(band_power))
    quality = 0.0 if total_band_power <= 0 else min(1.0, peak_power / total_band_power)

    bpm = float(band_freqs[peak_idx] * 60.0)
    return bpm, quality
