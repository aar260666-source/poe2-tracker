from pydantic import BaseModel, ConfigDict, Field


class TrackAddIn(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    league: str = Field(default="Standard", max_length=64)


class TrackedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    league: str


class LadderEntryOut(BaseModel):
    rank: int
    name: str
    level: int
    char_class: str
    dead: bool = False


class LadderWindowOut(BaseModel):
    above: LadderEntryOut | None
    current: LadderEntryOut
    below: LadderEntryOut | None
