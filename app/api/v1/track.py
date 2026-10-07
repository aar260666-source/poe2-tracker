from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import track as crud_track
from app.models.track import TrackedCharacter
from app.schemas.track import LadderWindowOut, TrackAddIn, TrackedOut
from app.services import ladder as ladder_service


router = APIRouter(prefix="/track", tags=["track"])


@router.get("/leagues", response_model=list[str])
async def leagues() -> list[str]:
    """Возвращает список доступных лиг из сервиса ladder."""
    return await ladder_service.get_leagues()


@router.post("", response_model=TrackedOut, status_code=201)
async def add_character(
        payload: TrackAddIn,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)) -> TrackedOut:

    """
     Добавляет персонажа в отслеживание: проверяет, что он найден в топ-1000 лиги
     через find_window, иначе 404; возвращает созданную запись (201).
    """
    window = await ladder_service.find_window(payload.league, payload.name)
    if window is None:
        raise HTTPException(404, "Персонаж не найден в этом лайдере — проверь имя и лигу")
    tracked = await crud_track.add(db, user.id, payload.name, payload.league)
    return TrackedOut.model_validate(tracked)


@router.get("", response_model=list[TrackedOut])
async def list_characters(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)) -> list[TrackedOut]:
    """Возвращает список всех отслеживаемых персонажей текущего пользователя."""
    rows = await crud_track.list_for_user(db, user.id)
    return [TrackedOut.model_validate(row) for row in rows]


@router.get("/{char_id}/ladder", response_model=LadderWindowOut)
async def character_position(
        char_id: int,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)) -> LadderWindowOut:
    """Проверяет принадлежность персонажа пользователю и возвращает его позицию в ладдере лиги"""
    row = await db.get(TrackedCharacter, char_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Персонаж не найден у этого пользователя")

    window = await ladder_service.find_window(row.league, row.name)
    if window is None:
        raise HTTPException(404, f"«{row.name}» сейчас не в топ-1000 лайдера")
    return window


@router.delete("/{char_id}", status_code=204)
async def remove_character(
        char_id: int,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)) -> None:
    """Удаляет персонажа из отслеживания пользователя"""
    if not await crud_track.delete(db, user.id, char_id):
        raise HTTPException(404, "Персонаж не найден у этого пользователя")
