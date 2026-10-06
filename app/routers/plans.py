from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.plan import Plan, PlanPrice
from app.schemas.commerce import PlanOut, PlanPriceOut

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.get("/", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    plans = (
        db.query(Plan)
        .options(joinedload(Plan.prices))
        .filter(Plan.is_active.is_(True))
        .order_by(Plan.sort_order.asc())
        .all()
    )

    return [
        PlanOut(
            id=plan.id,
            slug=plan.slug,
            name=plan.name,
            description=plan.description,
            features=plan.features or [],
            is_popular=plan.is_popular,
            prices=[
                PlanPriceOut.model_validate(price)
                for price in sorted(
                    [p for p in plan.prices if p.is_active],
                    key=lambda item: 0 if item.billing_interval == "monthly" else 1,
                )
            ],
        )
        for plan in plans
    ]


@router.get("/{plan_slug}", response_model=PlanOut)
def get_plan(plan_slug: str, db: Session = Depends(get_db)):
    plan = (
        db.query(Plan)
        .options(joinedload(Plan.prices))
        .filter(Plan.slug == plan_slug, Plan.is_active.is_(True))
        .first()
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    return PlanOut(
        id=plan.id,
        slug=plan.slug,
        name=plan.name,
        description=plan.description,
        features=plan.features or [],
        is_popular=plan.is_popular,
        prices=[
            PlanPriceOut.model_validate(price)
            for price in sorted(
                [p for p in plan.prices if p.is_active],
                key=lambda item: 0 if item.billing_interval == "monthly" else 1,
            )
        ],
    )
