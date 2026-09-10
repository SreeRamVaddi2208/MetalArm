"""Body measurements: weight, body fat, and custom metrics.

Tracking only - measurements never earn points, since logging one takes no
effort and could be repeated endlessly.
"""

import datetime as dt
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.workout import BodyMeasurement
from app.models.workout_enums import MeasurementMetric
from app.schemas.workout import BodyMeasurementCreate, BodyMeasurementOut

router = APIRouter(prefix="/body-measurements", tags=["body"])


@router.get("", response_model=list[BodyMeasurementOut])
def list_measurements(
    current_user: CurrentUser,
    db: DbSession,
    metric: MeasurementMetric | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[BodyMeasurementOut]:
    """Newest first."""
    query = select(BodyMeasurement).where(BodyMeasurement.user_id == current_user.id)
    if metric is not None:
        query = query.where(BodyMeasurement.metric == metric.value)
    rows = db.scalars(query.order_by(BodyMeasurement.recorded_at.desc()).limit(limit))
    return [BodyMeasurementOut.model_validate(r) for r in rows]


@router.post("", response_model=BodyMeasurementOut, status_code=status.HTTP_201_CREATED)
def create_measurement(
    payload: BodyMeasurementCreate, current_user: CurrentUser, db: DbSession
) -> BodyMeasurementOut:
    row = BodyMeasurement(
        user_id=current_user.id,
        metric=payload.metric.value,
        label=payload.label.strip() if payload.label else None,
        value=Decimal(str(payload.value)).quantize(Decimal("0.01")),
        unit=payload.unit.value,
        recorded_at=payload.recorded_at or dt.datetime.now(dt.timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return BodyMeasurementOut.model_validate(row)


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_measurement(
    measurement_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    row = db.execute(
        select(BodyMeasurement).where(
            BodyMeasurement.id == measurement_id,
            BodyMeasurement.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Measurement not found")
    db.delete(row)
    db.commit()
