from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    ``dict`` / ``list`` annotations map to JSON columns so SQLAlchemy can resolve
    them without repeating ``mapped_column(JSON)`` everywhere.
    """

    type_annotation_map = {dict: JSON, list: JSON}
