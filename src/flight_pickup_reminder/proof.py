import base64
import mimetypes
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from openai import OpenAI
from PIL import Image
from PIL.ExifTags import TAGS
from pydantic import BaseModel, Field

from .config import Settings
from .location_proof import TELEGRAM_LIVE_LOCATION_FOREVER_SECONDS, evaluate_telegram_location
from .models import ExifEvidence, LocationProofResult, ProofResult, VisionEvidence
from .providers.twilio_gateway import TwilioGateway
from .time_utils import utc_now


__all__ = ["ProofEvaluator", "TELEGRAM_LIVE_LOCATION_FOREVER_SECONDS", "VisionVerdict"]


class VisionVerdict(BaseModel):
    in_car: bool = Field(description="True if the image appears to be taken from inside or immediately beside a car.")
    on_road: bool = Field(description="True if the image shows the car is on a road or actively travelling.")
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: List[str]


def _parse_exif_datetime(value: Any, zone_name: str) -> Optional[datetime]:
    if not value:
        return None
    text = str(value)
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=ZoneInfo(zone_name))
        except ValueError:
            continue
    return None


def _exif_map(image: Image.Image) -> Dict[str, Any]:
    exif = image.getexif()
    mapped: Dict[str, Any] = {}
    for tag_id, value in exif.items():
        mapped[str(TAGS.get(tag_id, tag_id))] = value
    return mapped


class ProofEvaluator:
    def __init__(self, settings: Settings, twilio: TwilioGateway) -> None:
        self.settings = settings
        self.twilio = twilio

    def evaluate_twilio_media(self, media_url: str, content_type: Optional[str]) -> ProofResult:
        response = self.twilio.download_media(media_url)
        resolved_type = content_type or response.headers.get("Content-Type") or "image/jpeg"
        media_path = self._store_media(response.content, resolved_type)
        return self.evaluate_file(media_path, resolved_type)

    def evaluate_file(self, media_path: str, content_type: Optional[str] = None) -> ProofResult:
        exif = self._check_exif(media_path)
        vision = self._check_vision(media_path, content_type)
        reasons: List[str] = []

        if self.settings.proof_require_iphone_exif and not exif.iphone_like:
            reasons.append("Required iPhone-like EXIF was not present")
        if self.settings.proof_require_iphone_exif and not exif.fresh:
            reasons.append("Required fresh EXIF capture time was not present")
        if not vision.in_car:
            reasons.append("Vision check did not confirm they are in a car")
        if not vision.on_road:
            reasons.append("Vision check did not confirm they are on the road")
        if vision.confidence < 0.65:
            reasons.append("Vision confidence was below threshold")

        metadata_ok = (exif.iphone_like and exif.fresh) or not self.settings.proof_require_iphone_exif
        accepted = metadata_ok and vision.in_car and vision.on_road and vision.confidence >= 0.65
        if accepted:
            reasons.append("Photo proof accepted")

        return ProofResult(
            accepted=accepted,
            media_path=media_path,
            exif=exif,
            vision=vision,
            reasons=reasons,
        )

    def evaluate_telegram_location(
        self,
        location: Dict[str, Any],
        metadata: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> LocationProofResult:
        return evaluate_telegram_location(self.settings, location, metadata, now=now)

    def _store_media(self, content: bytes, content_type: str) -> str:
        os.makedirs(self.settings.proof_store_dir, exist_ok=True)
        extension = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".jpg"
        filename = utc_now().strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid.uuid4()) + extension
        path = os.path.join(self.settings.proof_store_dir, filename)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def _check_exif(self, media_path: str) -> ExifEvidence:
        reasons: List[str] = []
        try:
            with Image.open(media_path) as image:
                metadata = _exif_map(image)
        except Exception as exc:
            return ExifEvidence(
                present=False,
                make=None,
                model=None,
                captured_at=None,
                gps_present=False,
                iphone_like=False,
                fresh=False,
                reasons=["Could not read EXIF: {}".format(exc)],
            )

        if not metadata:
            return ExifEvidence(
                present=False,
                make=None,
                model=None,
                captured_at=None,
                gps_present=False,
                iphone_like=False,
                fresh=False,
                reasons=["No EXIF metadata found"],
            )

        make = str(metadata.get("Make", "") or "")
        model = str(metadata.get("Model", "") or "")
        captured_at = _parse_exif_datetime(
            metadata.get("DateTimeOriginal") or metadata.get("DateTime"),
            self.settings.app_timezone,
        )
        gps_present = "GPSInfo" in metadata
        iphone_like = "apple" in make.lower() or "iphone" in model.lower()
        fresh = False
        if captured_at:
            now = datetime.now(ZoneInfo(self.settings.app_timezone))
            fresh = abs(now - captured_at) <= timedelta(minutes=self.settings.proof_max_age_minutes)
        else:
            reasons.append("EXIF capture time missing")
        if not iphone_like:
            reasons.append("EXIF camera make/model did not look like iPhone")
        if not gps_present:
            reasons.append("EXIF GPS missing")

        return ExifEvidence(
            present=True,
            make=make or None,
            model=model or None,
            captured_at=captured_at,
            gps_present=gps_present,
            iphone_like=iphone_like,
            fresh=fresh,
            reasons=reasons,
        )

    def _check_vision(self, media_path: str, content_type: Optional[str]) -> VisionEvidence:
        if self.settings.proof_mock_mode in {"accept", "reject"}:
            accepted = self.settings.proof_mock_mode == "accept"
            return VisionEvidence(
                checked=True,
                in_car=accepted,
                on_road=accepted,
                confidence=0.99 if accepted else 0.05,
                reasons=["PROOF_MOCK_MODE={}".format(self.settings.proof_mock_mode)],
            )
        if not self.settings.openai_api_key:
            return VisionEvidence(
                checked=False,
                in_car=False,
                on_road=False,
                confidence=0.0,
                reasons=[],
                error="OPENAI_API_KEY is not configured",
            )

        media_type = content_type or mimetypes.guess_type(media_path)[0] or "image/jpeg"
        try:
            with open(media_path, "rb") as handle:
                image_b64 = base64.b64encode(handle.read()).decode("ascii")
            client = OpenAI(api_key=self.settings.openai_api_key)
            response = client.responses.parse(
                model=self.settings.openai_vision_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You check ride pickup proof photos. Do not identify people. "
                            "Return whether the image shows someone in a car and on a road."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Evaluate this proof photo. It should show the recipient is in a car "
                                    "and the vehicle is on a road or actively travelling."
                                ),
                            },
                            {
                                "type": "input_image",
                                "image_url": "data:{};base64,{}".format(media_type, image_b64),
                                "detail": "high",
                            },
                        ],
                    },
                ],
                text_format=VisionVerdict,
            )
            parsed = self._extract_parsed(response)
            if parsed is None:
                raise RuntimeError("OpenAI response did not include parsed vision output")
            return VisionEvidence(
                checked=True,
                in_car=parsed.in_car,
                on_road=parsed.on_road,
                confidence=parsed.confidence,
                reasons=parsed.reasons,
            )
        except Exception as exc:
            return VisionEvidence(
                checked=True,
                in_car=False,
                on_road=False,
                confidence=0.0,
                reasons=[],
                error=str(exc),
            )

    @staticmethod
    def _extract_parsed(response: Any) -> Optional[VisionVerdict]:
        output_parsed = getattr(response, "output_parsed", None)
        if output_parsed is not None:
            return output_parsed
        for output in getattr(response, "output", []) or []:
            for item in getattr(output, "content", []) or []:
                parsed = getattr(item, "parsed", None)
                if parsed is not None:
                    return parsed
        return None
