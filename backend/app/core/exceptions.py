from typing import Any, Optional
from fastapi import HTTPException, status

class CustomException(HTTPException):
    def __init__(
        self,
        code: int = 400,
        message: str = "Request error",
        data: Optional[Any] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "data": data}
        )

class UnauthorizedException(CustomException):
    def __init__(self, message: str = "Invalid credentials or token expired"):
        super().__init__(
            code=401,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )

class ForbiddenException(CustomException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            code=403,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )

class NotFoundException(CustomException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            code=404,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND
        )
