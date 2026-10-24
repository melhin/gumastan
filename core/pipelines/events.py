"""Event extraction task configuration.

Extracts calendar events (title, date, time, location, description)
from screenshots of event listings, tickets, flyers, etc.
"""

from pydantic import BaseModel, Field

from core.extraction.pipeline import TaskConfig


class Event(BaseModel):
    """Extracted calendar event."""

    title: str = Field(description="Short title / name of the event")
    start_date: str = Field(
        description="Event start date in YYYY-MM-DD format. Assume year is 2026 if the image does not specify."
    )
    start_time: str = Field(description="Event start time in HH:MM 24-hour format")
    end_time: str | None = Field(
        default=None,
        description="Event end time in HH:MM 24-hour format, if visible. Null if not present.",
    )
    location: str | None = Field(
        default=None,
        description="Venue name and address, if visible. Null if not present.",
    )
    description: str | None = Field(
        description="Any remaining relevant information (language, age restriction, notes, etc.)"
    )


EVENT_SYSTEM = (
    "You are a strict data extractor. Analyze the text and return valid JSON only. "
    "Do not include any conversational text before or after the JSON block. "
    "Use null for fields that are not present in the text. "
    "Assume the year is 2026. /no_think"
)

EVENT_SCHEMA = (
    '{"title": string, "start_date": "YYYY-MM-DD", "start_time": "HH:MM", '
    '"end_time": "HH:MM" or null, "location": string or null, "description": string}'
)

EVENT_USER = (
    "Extract the event as JSON matching this schema:\n{schema}\n\nText:\n{text}"
)

EVENT_TASK = TaskConfig(
    name="event",
    system_prompt=EVENT_SYSTEM,
    response_model=Event,
    user_template=EVENT_USER,
    schema_str=EVENT_SCHEMA,
    max_new_tokens=200,
)
