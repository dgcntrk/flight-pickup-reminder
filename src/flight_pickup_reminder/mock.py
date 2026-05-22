from datetime import datetime, timezone
from typing import List

from .models import ExifEvidence, ProofResult, VisionEvidence


def mock_proof(accepted: bool, reason: str = "manual mock proof") -> ProofResult:
    reasons: List[str]
    if accepted:
        reasons = ["Mock photo proof accepted", reason]
    else:
        reasons = ["Mock photo proof rejected", reason]
    return ProofResult(
        accepted=accepted,
        media_path="mock://proof",
        exif=ExifEvidence(
            present=True,
            make="Apple",
            model="iPhone",
            captured_at=datetime.now(timezone.utc),
            gps_present=True,
            iphone_like=True,
            fresh=True,
            reasons=["mock EXIF"],
        ),
        vision=VisionEvidence(
            checked=True,
            in_car=accepted,
            on_road=accepted,
            confidence=0.99 if accepted else 0.1,
            reasons=["mock vision decision"],
        ),
        reasons=reasons,
    )
