from datetime import datetime, timezone

from PIL import Image

from flight_pickup_reminder.proof import ProofEvaluator


class NoopTwilio:
    pass


def test_mock_proof_mode_accepts_plain_image_when_exif_not_required(settings_factory, tmp_path):
    settings = settings_factory(proof_mock_mode="accept", proof_require_iphone_exif=False)
    image_path = tmp_path / "proof.jpg"
    Image.new("RGB", (80, 80), color=(20, 80, 120)).save(image_path)

    proof = ProofEvaluator(settings, NoopTwilio()).evaluate_file(str(image_path), "image/jpeg")

    assert proof.accepted is True
    assert proof.vision.in_car is True
    assert proof.vision.on_road is True


def test_missing_openai_key_rejects_real_vision_mode(settings_factory, tmp_path):
    settings = settings_factory(proof_mock_mode="off", proof_require_iphone_exif=False)
    image_path = tmp_path / "proof.jpg"
    Image.new("RGB", (80, 80), color=(20, 80, 120)).save(image_path)

    proof = ProofEvaluator(settings, NoopTwilio()).evaluate_file(str(image_path), "image/jpeg")

    assert proof.accepted is False
    assert proof.vision.error == "OPENAI_API_KEY is not configured"


def test_active_telegram_live_location_is_accepted(settings_factory):
    settings = settings_factory(proof_accept_telegram_location=True)
    now = datetime(2026, 5, 15, 16, 0, tzinfo=timezone.utc)
    location = {
        "latitude": 49.025,
        "longitude": -122.36,
        "live_period": 900,
        "horizontal_accuracy": 25,
    }
    metadata = {"date": int(now.timestamp()) - 60, "edit_date": int(now.timestamp()) - 30}

    proof = ProofEvaluator(settings, NoopTwilio()).evaluate_telegram_location(location, metadata, now=now)

    assert proof.accepted is True
    assert proof.location.live is True
    assert proof.location.fresh is True


def test_telegram_live_location_requires_movement_when_enabled(settings_factory):
    settings = settings_factory(
        proof_accept_telegram_location=True,
        proof_require_telegram_movement=True,
        telegram_location_min_movement_meters=25,
    )
    now = datetime(2026, 5, 15, 16, 0, tzinfo=timezone.utc)
    location = {
        "latitude": 49.025,
        "longitude": -122.36,
        "live_period": 900,
        "horizontal_accuracy": 25,
    }
    metadata = {"date": int(now.timestamp()) - 60, "edit_date": int(now.timestamp()) - 30}

    proof = ProofEvaluator(settings, NoopTwilio()).evaluate_telegram_location(location, metadata, now=now)

    assert proof.accepted is False
    assert proof.location.moving is False
    assert any("has not updated with movement" in reason for reason in proof.reasons)


def test_telegram_live_location_accepts_movement_when_required(settings_factory):
    settings = settings_factory(
        proof_accept_telegram_location=True,
        proof_require_telegram_movement=True,
        telegram_location_min_movement_meters=25,
    )
    now = datetime(2026, 5, 15, 16, 0, tzinfo=timezone.utc)
    location = {
        "latitude": 49.025,
        "longitude": -122.36,
        "live_period": 900,
        "horizontal_accuracy": 25,
    }
    metadata = {
        "date": int(now.timestamp()) - 60,
        "edit_date": int(now.timestamp()) - 30,
        "movement_meters": 45,
    }

    proof = ProofEvaluator(settings, NoopTwilio()).evaluate_telegram_location(location, metadata, now=now)

    assert proof.accepted is True
    assert proof.location.moving is True


def test_telegram_location_rejects_outside_pickup_area(settings_factory):
    settings = settings_factory(
        proof_accept_telegram_location=True,
        proof_require_telegram_pickup_area=True,
        telegram_pickup_latitude=49.1752627,
        telegram_pickup_longitude=-121.9501248,
        telegram_pickup_radius_meters=15000,
    )
    now = datetime(2026, 5, 15, 16, 0, tzinfo=timezone.utc)
    location = {
        "latitude": 53.308728,
        "longitude": -113.58585,
        "live_period": 900,
        "horizontal_accuracy": 25,
    }
    metadata = {"date": int(now.timestamp()) - 60, "edit_date": int(now.timestamp()) - 30}

    proof = ProofEvaluator(settings, NoopTwilio()).evaluate_telegram_location(location, metadata, now=now)

    assert proof.accepted is False
    assert proof.location.near_pickup is False
    assert proof.location.pickup_distance_meters > 500000
    assert any("outside the configured pickup area" in reason for reason in proof.reasons)


def test_telegram_location_accepts_inside_pickup_area(settings_factory):
    settings = settings_factory(
        proof_accept_telegram_location=True,
        proof_require_telegram_pickup_area=True,
        telegram_pickup_latitude=49.1752627,
        telegram_pickup_longitude=-121.9501248,
        telegram_pickup_radius_meters=15000,
    )
    now = datetime(2026, 5, 15, 16, 0, tzinfo=timezone.utc)
    location = {
        "latitude": 49.1753,
        "longitude": -121.9501,
        "live_period": 900,
        "horizontal_accuracy": 25,
    }
    metadata = {"date": int(now.timestamp()) - 60, "edit_date": int(now.timestamp()) - 30}

    proof = ProofEvaluator(settings, NoopTwilio()).evaluate_telegram_location(location, metadata, now=now)

    assert proof.accepted is True
    assert proof.location.near_pickup is True


def test_static_telegram_location_rejected_when_live_required(settings_factory):
    settings = settings_factory(proof_accept_telegram_location=True)
    now = datetime(2026, 5, 15, 16, 0, tzinfo=timezone.utc)
    location = {"latitude": 49.025, "longitude": -122.36, "horizontal_accuracy": 25}
    metadata = {"date": int(now.timestamp())}

    proof = ProofEvaluator(settings, NoopTwilio()).evaluate_telegram_location(location, metadata, now=now)

    assert proof.accepted is False
    assert any("live location is required" in reason for reason in proof.reasons)


def test_telegram_location_accuracy_limit_rejects_broad_location(settings_factory):
    settings = settings_factory(
        proof_accept_telegram_location=True,
        telegram_location_max_accuracy_meters=100,
    )
    now = datetime(2026, 5, 15, 16, 0, tzinfo=timezone.utc)
    location = {
        "latitude": 49.025,
        "longitude": -122.36,
        "live_period": 900,
        "horizontal_accuracy": 300,
    }
    metadata = {"date": int(now.timestamp())}

    proof = ProofEvaluator(settings, NoopTwilio()).evaluate_telegram_location(location, metadata, now=now)

    assert proof.accepted is False
    assert proof.location.accuracy_ok is False
