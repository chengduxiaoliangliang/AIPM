from typing import Optional, List
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_token: Optional[str] = None

class SliderCaptchaResponse(BaseModel):
    captcha_id: str
    bg_image: str
    slider_image: str
    y: int
    block_width: int
    block_height: int

class SliderVerifyRequest(BaseModel):
    captcha_id: str
    x: float
    track: List[List[float]] = []

class SliderVerifyResponse(BaseModel):
    success: bool
    captcha_token: Optional[str] = None
    elapsed_time: Optional[float] = None
    message: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None

class UserInfoResponse(BaseModel):
    id: int
    username: str
    nickname: str
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    position: Optional[str] = None
    is_superuser: bool
    roles: List[str] = []
    permissions: List[str] = []
    department_id: Optional[int] = None
    department_name: Optional[str] = None
