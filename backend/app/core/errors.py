class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class InvalidInputError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class PayloadTooLargeError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=413)


class UnsupportedMediaError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=415)


class ClientDisconnectedError(AppError):
    def __init__(self, message: str = "Upload was cancelled.") -> None:
        super().__init__(message, status_code=499)


class ImportInProgressError(AppError):
    def __init__(
        self,
        message: str = "Another video import is already in progress. Please wait and try again.",
    ) -> None:
        super().__init__(message, status_code=409)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(message, status_code=404)


class JobConflictError(AppError):
    def __init__(
        self,
        message: str = "This video already has a processing job in progress.",
    ) -> None:
        super().__init__(message, status_code=409)


class PortraitNotReadyError(AppError):
    def __init__(
        self,
        message: str = "The portrait for this clip is not ready yet.",
    ) -> None:
        super().__init__(message, status_code=409)


class JobQueueFullError(AppError):
    def __init__(
        self,
        message: str = "Too many processing jobs are waiting. Please try again shortly.",
    ) -> None:
        super().__init__(message, status_code=503)


class MediaProcessingError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)
