import mimetypes
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..config import Settings
from ..time_utils import parse_iso_datetime, utc_now


class TelegramGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.telegram_bot_token)

    def get_me(self) -> Dict[str, Any]:
        return self._post("getMe")

    def get_updates(self, offset: Optional[int] = None, timeout: int = 0) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message", "edited_message"],
        }
        if offset is not None:
            payload["offset"] = offset
        data = self._post("getUpdates", json=payload)
        return data.get("result", [])

    def extract_update_location(self, update: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        message, source_update_type = self._message_from_update(update)
        location = message.get("location") if message else None
        if not location:
            return None
        metadata = {
            "update_id": update.get("update_id"),
            "message_id": message.get("message_id"),
            "date": message.get("date"),
            "edit_date": message.get("edit_date"),
            "from": message.get("from", {}),
            "chat": message.get("chat", {}),
            "source_type": "location",
            "source_update_type": source_update_type,
        }
        return location, metadata

    def download_update_media(self, update: Dict[str, Any], directory: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        message, _source_update_type = self._message_from_update(update)
        media = self._select_media(message)
        if media is None:
            return None

        file_id, file_name, content_type, source_type = media
        file_info = self._post("getFile", json={"file_id": file_id}).get("result", {})
        file_path = file_info.get("file_path")
        if not file_path:
            raise RuntimeError("Telegram did not return file_path for uploaded media")

        download_url = "https://api.telegram.org/file/bot{}/{}".format(
            self.settings.telegram_bot_token,
            file_path,
        )
        response = requests.get(download_url, timeout=30)
        response.raise_for_status()

        os.makedirs(directory, exist_ok=True)
        extension = self._extension(file_name, content_type, file_path)
        local_name = utc_now().strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid.uuid4()) + extension
        local_path = os.path.join(directory, local_name)
        with open(local_path, "wb") as handle:
            handle.write(response.content)

        metadata = {
            "update_id": update.get("update_id"),
            "message_id": message.get("message_id"),
            "from": message.get("from", {}),
            "chat": message.get("chat", {}),
            "source_type": source_type,
            "file_id": file_id,
            "file_name": file_name,
            "content_type": content_type,
        }
        return local_path, content_type, metadata

    def allowed_sender(self, update: Dict[str, Any]) -> bool:
        if self._allow_any_active():
            return True
        if not self.settings.telegram_allowed_user_ids:
            return True
        message, _source_update_type = self._message_from_update(update)
        sender = message.get("from") or {}
        sender_id = sender.get("id")
        return sender_id in self.settings.telegram_allowed_user_ids

    def extract_sender_id(self, update: Dict[str, Any]) -> Optional[int]:
        message, _source_update_type = self._message_from_update(update)
        sender = message.get("from") or {}
        sender_id = sender.get("id")
        if isinstance(sender_id, int):
            return sender_id
        return None

    def _post(self, method: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        response = requests.post(
            "https://api.telegram.org/bot{}/{}".format(self.settings.telegram_bot_token, method),
            json=json,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError("Telegram {} failed: {}".format(method, data))
        return data

    def _allow_any_active(self) -> bool:
        if not self.settings.telegram_allow_any_until:
            return False
        until = parse_iso_datetime(self.settings.telegram_allow_any_until)
        if until is None:
            return False
        return utc_now() <= until

    @staticmethod
    def _message_from_update(update: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
        if update.get("message"):
            return update["message"], "message"
        if update.get("edited_message"):
            return update["edited_message"], "edited_message"
        return {}, None

    @staticmethod
    def _select_media(message: Dict[str, Any]) -> Optional[Tuple[str, Optional[str], str, str]]:
        document = message.get("document")
        if document:
            content_type = document.get("mime_type") or "application/octet-stream"
            return (
                document["file_id"],
                document.get("file_name"),
                content_type,
                "document",
            )

        photos = message.get("photo") or []
        if photos:
            best = sorted(photos, key=lambda item: item.get("file_size", 0))[-1]
            return (best["file_id"], None, "image/jpeg", "photo")
        return None

    @staticmethod
    def _extension(file_name: Optional[str], content_type: str, file_path: str) -> str:
        if file_name:
            _, extension = os.path.splitext(file_name)
            if extension:
                return extension
        _, extension = os.path.splitext(file_path)
        if extension:
            return extension
        return mimetypes.guess_extension(content_type) or ".bin"
