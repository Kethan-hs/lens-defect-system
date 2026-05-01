"""
Pydantic schemas for API responses.
These decouple the SQLAlchemy ORM models from the JSON the API returns,
fixing the raw-ORM-serialization bug and giving proper validation.
"""
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
import json


class InspectionResponse(BaseModel):
    id:           int
    timestamp:    datetime
    pass_fail:    str
    defects_json: str
    frame_path:   Optional[str] = None

    model_config = {"from_attributes": True}

    @field_validator("defects_json")
    @classmethod
    def validate_json(cls, v):
        """Ensure defects_json is always valid JSON."""
        try:
            json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return "[]"
        return v


class StatsResponse(BaseModel):
    total:         int
    pass_count:    int
    fail_count:    int
    defect_counts: dict[str, int]
