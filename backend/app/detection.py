from dataclasses import dataclass


@dataclass
class PresenceUpdate:
    occupied: bool
    confidence: float
    changed: bool


class PresenceDetector:
    def __init__(self, threshold: float, debounce_samples: int) -> None:
        self.threshold = max(1e-9, threshold)
        self.debounce_samples = max(1, debounce_samples)
        self._occupied = False
        self._hits = 0
        self._misses = 0

    @property
    def occupied(self) -> bool:
        return self._occupied

    def update(self, variance: float) -> PresenceUpdate:
        ratio = variance / self.threshold
        changed = False

        if variance >= self.threshold:
            self._hits += 1
            self._misses = 0
            if not self._occupied and self._hits >= self.debounce_samples:
                self._occupied = True
                changed = True
        else:
            self._misses += 1
            self._hits = 0
            if self._occupied and self._misses >= self.debounce_samples:
                self._occupied = False
                changed = True

        if self._occupied:
            confidence = min(1.0, ratio)
        else:
            confidence = min(1.0, max(0.05, 1.0 - ratio))

        return PresenceUpdate(occupied=self._occupied, confidence=confidence, changed=changed)
