from flight_pickup_reminder.mock import mock_proof
from flight_pickup_reminder.models import LocationEvidence, LocationProofResult
from flight_pickup_reminder.providers.telegram_gateway import TelegramGateway
from flight_pickup_reminder.telegram_intake import TelegramProofIntake
from flight_pickup_reminder.state import StateStore


class FakeGateway:
    configured = True

    def __init__(self, updates, allowed=True):
        self.updates = updates
        self.allowed = allowed
        self.downloaded = 0

    def get_updates(self, offset=None, timeout=0):
        return self.updates

    def allowed_sender(self, update):
        return self.allowed

    def extract_sender_id(self, update):
        return update["message"]["from"]["id"]

    def extract_update_location(self, update):
        message = update["message"]
        if "location" not in message:
            return None
        return message["location"], {"source_update_type": "message", "date": message.get("date")}

    def download_update_media(self, update, directory):
        if "photo" not in update["message"] and "document" not in update["message"]:
            return None
        self.downloaded += 1
        return "/tmp/proof.jpg", "image/jpeg", {"source_type": "photo", "file_name": None}


class FakeProofEvaluator:
    def __init__(self, settings):
        self.settings = settings

    def evaluate_file(self, media_path, content_type=None):
        return mock_proof(True)

    def evaluate_telegram_location(self, location, metadata):
        movement_meters = metadata.get("movement_meters")
        return LocationProofResult(
            accepted=True,
            source="telegram_location",
            location=LocationEvidence(
                latitude=location["latitude"],
                longitude=location["longitude"],
                horizontal_accuracy=location.get("horizontal_accuracy"),
                live=True,
                live_period_seconds=location.get("live_period"),
                sent_at=None,
                updated_at=None,
                active_until=None,
                fresh=True,
                active=True,
                accuracy_ok=True,
                movement_meters=movement_meters,
                moving=movement_meters is not None and movement_meters > 25,
                pickup_distance_meters=None,
                near_pickup=True,
                reasons=["fake location proof"],
            ),
            reasons=["fake location proof accepted"],
        )


class FakeOrchestrator:
    def __init__(self, store):
        self.store = store

    def record_proof(self, proof):
        state = self.store.load()
        state["proof"] = proof
        state["proof_accepted"] = proof.accepted
        self.store.save(state)
        self.store.append_event("proof_received", {"accepted": proof.accepted})
        return self.store.load()


def test_telegram_poll_accepts_allowed_media(settings):
    store = StateStore(settings.state_path)
    store.save(StateStore.default_state())
    update = {
        "update_id": 10,
        "message": {
            "message_id": 1,
            "from": {"id": 1234},
            "chat": {"id": 1234},
            "photo": [{"file_id": "a", "file_size": 10}, {"file_id": "b", "file_size": 20}],
        },
    }
    gateway = FakeGateway([update])
    intake = TelegramProofIntake(gateway, FakeProofEvaluator(settings), FakeOrchestrator(store), store)

    state = intake.poll_once()

    assert state["telegram_update_offset"] == 11
    assert state["proof_accepted"] is True
    assert gateway.downloaded == 1
    assert state["events"][-1]["type"] == "telegram_poll"


def test_telegram_poll_rejects_disallowed_sender(settings):
    store = StateStore(settings.state_path)
    store.save(StateStore.default_state())
    update = {
        "update_id": 11,
        "message": {
            "message_id": 1,
            "from": {"id": 9999},
            "chat": {"id": 9999},
            "photo": [{"file_id": "a", "file_size": 10}],
        },
    }
    gateway = FakeGateway([update], allowed=False)
    intake = TelegramProofIntake(gateway, FakeProofEvaluator(settings), FakeOrchestrator(store), store)

    state = intake.poll_once()

    assert state["telegram_update_offset"] == 12
    assert state["proof_accepted"] is False
    assert gateway.downloaded == 0
    assert any(event["type"] == "telegram_rejected_sender" for event in state["events"])


def test_telegram_poll_accepts_allowed_live_location(settings_factory):
    settings = settings_factory(proof_accept_telegram_location=True)
    store = StateStore(settings.state_path)
    store.save(StateStore.default_state())
    update = {
        "update_id": 12,
        "message": {
            "message_id": 1,
            "date": 1778855700,
            "from": {"id": 1234},
            "chat": {"id": 1234},
            "location": {
                "latitude": 49.025,
                "longitude": -122.36,
                "live_period": 900,
                "horizontal_accuracy": 30,
            },
        },
    }
    gateway = FakeGateway([update])
    intake = TelegramProofIntake(gateway, FakeProofEvaluator(settings), FakeOrchestrator(store), store)

    state = intake.poll_once()

    assert state["telegram_update_offset"] == 13
    assert state["proof_accepted"] is True
    assert gateway.downloaded == 0
    assert any(event["type"] == "telegram_location_received" for event in state["events"])


def test_telegram_live_location_tracks_movement(settings_factory):
    settings = settings_factory(proof_accept_telegram_location=True)
    store = StateStore(settings.state_path)
    store.save(StateStore.default_state())
    updates = [
        {
            "update_id": 12,
            "message": {
                "message_id": 1,
                "date": 1778855700,
                "from": {"id": 1234},
                "chat": {"id": 1234},
                "location": {
                    "latitude": 49.025,
                    "longitude": -122.36,
                    "live_period": 900,
                    "horizontal_accuracy": 30,
                },
            },
        },
        {
            "update_id": 13,
            "message": {
                "message_id": 1,
                "date": 1778855700,
                "from": {"id": 1234},
                "chat": {"id": 1234},
                "location": {
                    "latitude": 49.026,
                    "longitude": -122.36,
                    "live_period": 900,
                    "horizontal_accuracy": 30,
                },
            },
        },
    ]
    gateway = FakeGateway(updates)
    intake = TelegramProofIntake(gateway, FakeProofEvaluator(settings), FakeOrchestrator(store), store)

    state = intake.poll_once()

    movement_events = [event for event in state["events"] if event["type"] == "telegram_location_received"]
    assert movement_events[-1]["payload"]["movement_meters"] > 100


def test_telegram_allow_any_until_allows_unknown_sender(settings_factory):
    settings = settings_factory(
        telegram_allowed_user_ids=[111],
        telegram_allow_any_until="2999-01-01T00:00:00+00:00",
    )
    update = {"message": {"from": {"id": 222}}}

    assert TelegramGateway(settings).allowed_sender(update) is True


def test_telegram_allow_any_until_expires(settings_factory):
    settings = settings_factory(
        telegram_allowed_user_ids=[111],
        telegram_allow_any_until="2000-01-01T00:00:00+00:00",
    )
    update = {"message": {"from": {"id": 222}}}

    assert TelegramGateway(settings).allowed_sender(update) is False
