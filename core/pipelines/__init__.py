"""Task configurations — prompts and schemas for different extraction tasks.

Adding a new task is one file with a TaskConfig; the model and OCR
layers are reused from :mod:`core.extraction`.
"""

from core.extraction.pipeline import TaskConfig
from core.pipelines.events import EVENT_TASK
from core.pipelines.events import Event

# Registry: task name → TaskConfig
TASKS: dict[str, "TaskConfig"] = {
    "event": EVENT_TASK,
}
