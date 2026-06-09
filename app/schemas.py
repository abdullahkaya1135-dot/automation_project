from pydantic import BaseModel, Field


class TourContextCreate(BaseModel):
    date: str | None = Field(default=None, max_length=32)
    ambient_temp: str = Field(..., min_length=1, max_length=64)
    production_engineer: str = Field(..., min_length=1, max_length=255)
    shift_chief: str = Field(..., min_length=1, max_length=255)
    shift: str | None = Field(default=None, max_length=64)
