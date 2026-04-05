class XAIError(Exception):
    pass


class XAIAuthError(XAIError):
    pass


class XAIValidationError(XAIError):
    pass


class XAIRateLimitError(XAIError):
    pass


class XAIServerError(XAIError):
    pass


class VideoGenerationError(XAIError):
    def __init__(self, message: str, payload: dict | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


class VideoGenerationTimeoutError(XAIError):
    def __init__(self, request_id: str, timeout_seconds: float) -> None:
        super().__init__(
            f"Polling timed out after {timeout_seconds}s for request_id={request_id}"
        )
        self.request_id = request_id
        self.timeout_seconds = timeout_seconds


class ImageGenerationError(XAIError):
    def __init__(self, message: str, payload: dict | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


class ImageBatchError(XAIError):
    def __init__(self, message: str, payload: dict | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


class ImageBatchTimeoutError(XAIError):
    def __init__(self, batch_id: str, timeout_seconds: float) -> None:
        super().__init__(
            f"Batch polling timed out after {timeout_seconds}s for batch_id={batch_id}"
        )
        self.batch_id = batch_id
        self.timeout_seconds = timeout_seconds


class ImageEditError(XAIError):
    def __init__(self, message: str, payload: dict | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}
