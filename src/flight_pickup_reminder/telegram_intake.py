from typing import Any, Dict, Optional

from .geo import distance_meters
from .orchestrator import ReminderOrchestrator
from .proof import ProofEvaluator
from .providers.telegram_gateway import TelegramGateway
from .state import StateStore


class TelegramProofIntake:
    def __init__(
        self,
        gateway: TelegramGateway,
        proof_evaluator: ProofEvaluator,
        orchestrator: ReminderOrchestrator,
        store: StateStore,
    ) -> None:
        self.gateway = gateway
        self.proof_evaluator = proof_evaluator
        self.orchestrator = orchestrator
        self.store = store

    def poll_once(self) -> Dict[str, Any]:
        if not self.gateway.configured:
            self.store.append_event("telegram_skipped", {"reason": "not_configured"})
            return self.store.load()

        state = self.store.load()
        offset = state.get("telegram_update_offset")
        updates = self.gateway.get_updates(offset=offset, timeout=0)
        processed = 0
        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                state["telegram_update_offset"] = update_id + 1
                self.store.save(state)
            self.handle_update(update)
            processed += 1
            state = self.store.load()

        if processed:
            self.store.append_event("telegram_poll", {"updates": processed})
        return self.store.load()

    def handle_update(self, update: Dict[str, Any]) -> Optional[Any]:
        sender_id = self.gateway.extract_sender_id(update)
        if not self.gateway.allowed_sender(update):
            self.store.append_event("telegram_rejected_sender", {"sender_id": sender_id})
            return None

        location_payload = self.gateway.extract_update_location(update)
        if location_payload is not None:
            location, metadata = location_payload
            if not self.proof_evaluator.settings.proof_accept_telegram_location:
                self.store.append_event("telegram_location_ignored", {"sender_id": sender_id, "reason": "not_enabled"})
                return None
            metadata.update(self._movement_metadata(sender_id, location, metadata))
            proof = self.proof_evaluator.evaluate_telegram_location(location, metadata)
            self._remember_location(sender_id, location, metadata)
            self.orchestrator.record_proof(proof)
            self.store.append_event(
                "telegram_location_received",
                {
                    "sender_id": sender_id,
                    "accepted": proof.accepted,
                    "live": proof.location.live,
                    "fresh": proof.location.fresh,
                    "active": proof.location.active,
                    "moving": proof.location.moving,
                    "movement_meters": proof.location.movement_meters,
                    "near_pickup": proof.location.near_pickup,
                    "pickup_distance_meters": proof.location.pickup_distance_meters,
                    "horizontal_accuracy": proof.location.horizontal_accuracy,
                    "source_update_type": metadata.get("source_update_type"),
                },
            )
            return proof

        media = self.gateway.download_update_media(update, self.proof_evaluator.settings.proof_store_dir)
        if media is None:
            self.store.append_event("telegram_message_without_media", {"sender_id": sender_id})
            return None

        media_path, content_type, metadata = media
        proof = self.proof_evaluator.evaluate_file(media_path, content_type)
        state = self.orchestrator.record_proof(proof)
        self.store.append_event(
            "telegram_proof_received",
            {
                "sender_id": sender_id,
                "accepted": state.get("proof_accepted", False),
                "source_type": metadata.get("source_type"),
                "file_name": metadata.get("file_name"),
            },
        )
        return proof

    def _movement_metadata(
        self,
        sender_id: Optional[int],
        location: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        previous = self.store.load().get("telegram_location_tracks", {}).get(
            self._track_key(sender_id, metadata)
        )
        if not previous:
            return {}
        movement = distance_meters(
            previous.get("latitude"),
            previous.get("longitude"),
            location.get("latitude"),
            location.get("longitude"),
        )
        if movement is None:
            return {}
        return {
            "previous_latitude": previous.get("latitude"),
            "previous_longitude": previous.get("longitude"),
            "movement_meters": movement,
        }

    def _remember_location(
        self,
        sender_id: Optional[int],
        location: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> None:
        key = self._track_key(sender_id, metadata)
        state = self.store.load()
        tracks = state.setdefault("telegram_location_tracks", {})
        tracks[key] = {
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "message_id": metadata.get("message_id"),
            "sender_id": sender_id,
            "updated_at": metadata.get("edit_date") or metadata.get("date"),
        }
        state["telegram_location_tracks"] = tracks
        self.store.save(state)

    @staticmethod
    def _track_key(sender_id: Optional[int], metadata: Dict[str, Any]) -> str:
        actor = sender_id or (metadata.get("chat") or {}).get("id") or "unknown"
        message_id = metadata.get("message_id") or "unknown"
        return "{}:{}".format(actor, message_id)
