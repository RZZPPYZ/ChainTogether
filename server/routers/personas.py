from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status

from ..auth import verify_token
from ..models import (
    PersonaImportRequest,
    PersonaRead,
    PersonaResourceContent,
    PersonaResourcesResponse,
)
from ..persona_manager import (
    MAX_PERSONA_ARCHIVE_BYTES,
    PersonaError,
    persona_manager,
)
from ..session_manager import session_manager

router = APIRouter(tags=["personas"])


def _http_error(error: PersonaError) -> HTTPException:
    return HTTPException(error.status_code, str(error))


@router.get("/api/personas", response_model=list[PersonaRead])
async def list_personas(_: str = Depends(verify_token)):
    return [PersonaRead(**p) for p in await persona_manager.list_personas()]


@router.post(
    "/api/personas/import",
    response_model=PersonaRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_persona(req: PersonaImportRequest, _: str = Depends(verify_token)):
    try:
        return PersonaRead(**(await persona_manager.import_github(req.source_url)))
    except PersonaError as error:
        raise _http_error(error)


@router.post(
    "/api/personas/import-zip",
    response_model=PersonaRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_persona_zip(
    file: UploadFile, _: str = Depends(verify_token)
):
    archive = await file.read(MAX_PERSONA_ARCHIVE_BYTES + 1)
    if len(archive) > MAX_PERSONA_ARCHIVE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "Persona package archive is larger than 25 MB",
        )
    try:
        return PersonaRead(
            **(await persona_manager.import_zip(archive, file.filename))
        )
    except PersonaError as error:
        raise _http_error(error)


@router.delete("/api/personas/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(persona_id: str, _: str = Depends(verify_token)):
    try:
        await persona_manager.delete_persona(persona_id)
    except PersonaError as error:
        raise _http_error(error)


async def _active_for_session(session_id: str):
    session = session_manager.get_session(session_id)
    if session is None or not session.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    persona = await persona_manager.active_for_agent(session.agent_id)
    if persona is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This agent has no active persona")
    return persona


@router.get(
    "/api/sessions/{session_id}/persona/resources",
    response_model=PersonaResourcesResponse,
)
async def list_persona_resources(session_id: str, _: str = Depends(verify_token)):
    persona = await _active_for_session(session_id)
    return PersonaResourcesResponse(
        persona_id=persona["id"],
        persona_name=persona["name"],
        resources=persona["resources"],
    )


@router.get(
    "/api/sessions/{session_id}/persona/resource",
    response_model=PersonaResourceContent,
)
async def read_persona_resource(
    session_id: str,
    path: str = Query(min_length=1),
    _: str = Depends(verify_token),
):
    persona = await _active_for_session(session_id)
    try:
        content = await persona_manager.read_resource(persona, path)
    except PersonaError as error:
        raise _http_error(error)
    return PersonaResourceContent(
        persona_id=persona["id"], path=path, content=content
    )
