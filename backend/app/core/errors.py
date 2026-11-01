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
