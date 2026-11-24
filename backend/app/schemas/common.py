from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Paginated(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int) -> "Paginated[T]":
        pages = max(1, (total + page_size - 1) // page_size) if total else 1
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class MessageResponse(BaseModel):
    success: bool = True
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    version: str
    environment: str
    demo_mode: bool
    timestamp: str
