from app.detection import PresenceDetector


def test_presence_detector_hysteresis_and_debounce() -> None:
    detector = PresenceDetector(
        threshold=1.0,
        debounce_samples=2,
        enter_multiplier=1.15,
        exit_multiplier=0.85,
        ema_alpha=1.0,
    )

    first_hit = detector.update(1.2)
    assert first_hit.occupied is False

    second_hit = detector.update(1.2)
    assert second_hit.occupied is True
    assert second_hit.changed is True

    near_threshold = detector.update(0.9)
    assert near_threshold.occupied is True

    first_miss = detector.update(0.7)
    assert first_miss.occupied is True

    second_miss = detector.update(0.7)
    assert second_miss.occupied is False
    assert second_miss.changed is True

