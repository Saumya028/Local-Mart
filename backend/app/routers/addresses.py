import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Address, Profile
from app.schemas.address import AddressCreate, AddressOut, AddressUpdate

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("", response_model=list[AddressOut])
async def list_addresses(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Address)
        .where(Address.user_id == user.id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=AddressOut)
async def create_address(
    payload: AddressCreate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.is_default:
        # Only one default address per user — clear the flag on any
        # existing ones before this one claims it.
        await db.execute(update(Address).where(Address.user_id == user.id).values(is_default=False))

    address = Address(id=uuid.uuid4(), user_id=user.id, **payload.model_dump())
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address


@router.put("/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: str,
    payload: AddressUpdate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    aid = parse_uuid_or_404(address_id, "Address")
    result = await db.execute(select(Address).where(Address.id == aid))
    address = result.scalar_one_or_none()

    # Scoped to the requesting user — one customer must never be able to
    # edit or even see another customer's saved address by guessing an ID.
    if address is None or address.user_id != user.id:
        raise HTTPException(status_code=404, detail="Address not found")

    updates = payload.model_dump(exclude_unset=True)

    if updates.get("is_default"):
        await db.execute(update(Address).where(Address.user_id == user.id).values(is_default=False))

    for key, value in updates.items():
        setattr(address, key, value)

    await db.commit()
    await db.refresh(address)
    return address


@router.delete("/{address_id}")
async def delete_address(
    address_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    aid = parse_uuid_or_404(address_id, "Address")
    result = await db.execute(select(Address).where(Address.id == aid))
    address = result.scalar_one_or_none()

    if address is None or address.user_id != user.id:
        raise HTTPException(status_code=404, detail="Address not found")

    await db.delete(address)
    await db.commit()
    return {"id": address_id, "deleted": True}
