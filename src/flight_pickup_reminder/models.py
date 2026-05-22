from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class FlightSnapshot:
    provider: str
    ident: str
    status: str
    arrival_eta: Optional[datetime]
    scheduled_arrival: Optional[datetime]
    actual_arrival: Optional[datetime]
    origin: str
    destination: str
    updated_at: datetime
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteSnapshot:
    provider: str
    duration_seconds: int
    static_duration_seconds: Optional[int]
    distance_meters: Optional[int]
    updated_at: datetime
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReminderPlan:
    arrival_eta: datetime
    route_duration_seconds: int
    target_airport_arrival_at: datetime
    leave_by: datetime
    call_start_at: datetime
    call_lead_minutes: int
    airport_buffer_minutes: int


@dataclass
class CallResult:
    to_number: str
    provider: str
    sid: Optional[str]
    status: str
    dry_run: bool
    message: str


@dataclass
class ExifEvidence:
    present: bool
    make: Optional[str]
    model: Optional[str]
    captured_at: Optional[datetime]
    gps_present: bool
    iphone_like: bool
    fresh: bool
    reasons: List[str]


@dataclass
class VisionEvidence:
    checked: bool
    in_car: bool
    on_road: bool
    confidence: float
    reasons: List[str]
    error: Optional[str] = None


@dataclass
class ProofResult:
    accepted: bool
    media_path: str
    exif: ExifEvidence
    vision: VisionEvidence
    reasons: List[str]


@dataclass
class LocationEvidence:
    latitude: float
    longitude: float
    horizontal_accuracy: Optional[float]
    live: bool
    live_period_seconds: Optional[int]
    sent_at: Optional[datetime]
    updated_at: Optional[datetime]
    active_until: Optional[datetime]
    fresh: bool
    active: bool
    accuracy_ok: bool
    movement_meters: Optional[float]
    moving: bool
    pickup_distance_meters: Optional[float]
    near_pickup: bool
    reasons: List[str]


@dataclass
class LocationProofResult:
    accepted: bool
    source: str
    location: LocationEvidence
    reasons: List[str]
