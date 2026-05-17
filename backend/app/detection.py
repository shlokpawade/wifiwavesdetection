from dataclasses import dataclass


@dataclass
class PresenceUpdate:
    occupied: bool
    confidence: float
    changed: bool


class PresenceDetector:
    def __init__(
        self,
        threshold: float,
        debounce_samples: int,
        enter_multiplier: float = 1.15,
        exit_multiplier: float = 0.85,
        ema_alpha: float = 0.2,
    ) -> None:
        self.threshold = max(1e-9, threshold)
        self.debounce_samples = max(1, debounce_samples)
        self.enter_multiplier = max(1.0, enter_multiplier)
        self.exit_multiplier = min(1.0, max(0.1, exit_multiplier))
        self.ema_alpha = min(1.0, max(0.05, ema_alpha))
        self._occupied = False
        self._hits = 0
        self._misses = 0
        self._smoothed_variance: float | None = None

    @property
    def occupied(self) -> bool:
        return self._occupied

    def update(self, variance: float) -> PresenceUpdate:
        if self._smoothed_variance is None:
            self._smoothed_variance = variance
        else:
            self._smoothed_variance = (
                self.ema_alpha * variance + (1.0 - self.ema_alpha) * self._smoothed_variance
            )

        smoothed_variance = self._smoothed_variance
        enter_threshold = self.threshold * self.enter_multiplier
        exit_threshold = self.threshold * self.exit_multiplier
        ratio = smoothed_variance / self.threshold
        changed = False

        if self._occupied:
            if smoothed_variance >= exit_threshold:
                self._hits += 1
                self._misses = 0
            else:
                self._misses += 1
                self._hits = 0
                if self._misses >= self.debounce_samples:
                    self._occupied = False
                    changed = True
        else:
            if smoothed_variance >= enter_threshold:
                self._hits += 1
                self._misses = 0
                if self._hits >= self.debounce_samples:
                    self._occupied = True
                    changed = True
            else:
                self._misses += 1
                self._hits = 0

        if self._occupied:
            confidence = min(1.0, smoothed_variance / max(1e-9, enter_threshold))
        else:
            confidence = min(1.0, max(0.05, 1.0 - (smoothed_variance / max(1e-9, exit_threshold))))

        return PresenceUpdate(occupied=self._occupied, confidence=confidence, changed=changed)
