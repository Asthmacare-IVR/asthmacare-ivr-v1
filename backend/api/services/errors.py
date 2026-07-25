from fastapi import HTTPException, status

from database.errors import (
    ConflictError,
    NotFoundError,
    RepositoryError,
    UnavailableError,
    ValidationFailureError,
)

from queue_engine.engine import (
    InvalidTransitionError,
    QueueEngineError,
)


def translate_repository_error(exc: RepositoryError):

    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        )

    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        )

    if isinstance(exc, ValidationFailureError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        )

    if isinstance(exc, UnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.message,
        )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=exc.message,
    )


def translate_engine_error(exc: QueueEngineError):

    if isinstance(exc, InvalidTransitionError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
    )