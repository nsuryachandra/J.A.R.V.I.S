"""Deterministic occurrence identity generator for recurring events."""

import hashlib
import json
from typing import Any, Dict, Optional
from uuid import UUID
from app.temporal.schemas import OccurrenceIdentity


class OccurrenceIdentityGenerator:
    """Generates immutable, collision-resistant deterministic identities for routine occurrences."""

    @classmethod
    def generate_key(
        cls,
        routine_id: UUID | str,
        rule_version: int,
        local_date_time: str,
        timezone: str,
        sequence_index: Optional[int] = None,
    ) -> str:
        """Create a deterministic SHA-256 key from canonical representation of occurrence coordinates."""
        canonical_dict: Dict[str, Any] = {
            "local_date_time": str(local_date_time).strip(),
            "routine_id": str(routine_id).lower(),
            "rule_version": int(rule_version),
            "sequence_index": sequence_index if sequence_index is not None else None,
            "timezone": str(timezone).strip(),
        }
        # Canonical JSON encoding with sorted keys and compact separators
        canonical_json = json.dumps(
            canonical_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def create_identity(
        cls,
        routine_id: UUID | str,
        rule_version: int,
        local_date_time: str,
        timezone: str,
        sequence_index: Optional[int] = None,
    ) -> OccurrenceIdentity:
        """Instantiate OccurrenceIdentity schema with computed SHA-256 key."""
        rid = UUID(str(routine_id)) if not isinstance(routine_id, UUID) else routine_id
        key = cls.generate_key(
            routine_id=rid,
            rule_version=rule_version,
            local_date_time=local_date_time,
            timezone=timezone,
            sequence_index=sequence_index,
        )
        return OccurrenceIdentity(
            occurrence_key=key,
            routine_id=rid,
            rule_version=rule_version,
            local_date_time=local_date_time,
            timezone=timezone,
            sequence_index=sequence_index,
        )
