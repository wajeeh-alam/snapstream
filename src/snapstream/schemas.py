"""Request and response contracts for the HTTP API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.rpartition("@")
        if not separator or not local or "." not in domain or domain.startswith("."):
            raise ValueError("invalid email address")
        return value

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display name must not be blank")
        return value


class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicUserResponse(BaseModel):
    id: str
    username: str
    display_name: str

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


class UploadPresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=127)
    size_bytes: int = Field(gt=0)

    @field_validator("content_type")
    @classmethod
    def normalize_content_type(cls, value: str) -> str:
        return value.strip().lower()


class MediaReference(BaseModel):
    key: str = Field(min_length=1, max_length=1024)
    content_type: str = Field(min_length=1, max_length=127)
    size_bytes: int = Field(gt=0)

    @field_validator("content_type")
    @classmethod
    def normalize_content_type(cls, value: str) -> str:
        return value.strip().lower()


class UploadPresignResponse(BaseModel):
    upload_url: str
    method: Literal["PUT"] = "PUT"
    bucket: str
    key: str
    headers: dict[str, str]
    expires_in: int


class MediaResponse(BaseModel):
    bucket: str
    key: str
    content_type: str
    size_bytes: int


class MediaDownloadResponse(BaseModel):
    download_url: str
    expires_in: int


class PostCreateRequest(BaseModel):
    body: str = Field(default="", max_length=2000)
    media: MediaReference | None = None

    @field_validator("body")
    @classmethod
    def strip_body(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_content(self) -> "PostCreateRequest":
        if not self.body and self.media is None:
            raise ValueError("a post must include text or media")
        return self


class PostResponse(BaseModel):
    id: str
    body: str
    likes_count: int
    created_at: datetime
    author: PublicUserResponse
    media: MediaResponse | None


class FeedResponse(BaseModel):
    kind: Literal["recent", "trending"]
    items: list[PostResponse]


class LikeResponse(BaseModel):
    post_id: str
    likes_count: int
    liked: bool


class FollowResponse(BaseModel):
    user_id: str
    following: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "not_ready"]
    checks: dict[str, Literal["ok", "error"]] | None = None
