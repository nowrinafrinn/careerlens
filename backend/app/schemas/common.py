from typing import Annotated, Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, HttpUrl, PlainSerializer, StringConstraints, model_validator

T = TypeVar("T")

# A required single-line text value: surrounding whitespace removed, never empty.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# Validated as an http(s) URL; written out (to the database and JSON) as a plain string.
Url = Annotated[HttpUrl, PlainSerializer(str, return_type=str)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PartialUpdate(BaseModel):
    """Base for PATCH bodies: only fields actually sent are applied.

    Sending `null` clears an optional field. Fields listed in
    `non_nullable` may be omitted but not set to null.
    """

    # ClassVar: configuration of the class, not a field clients can send.
    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_nulls(self) -> "PartialUpdate":
        cleared = [f for f in self.non_nullable if f in self.model_fields_set and getattr(self, f) is None]
        if cleared:
            raise ValueError(f"These fields can't be empty: {', '.join(sorted(cleared))}")
        return self

    def changes(self, *, exclude: set[str] | None = None) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True, exclude=exclude)
