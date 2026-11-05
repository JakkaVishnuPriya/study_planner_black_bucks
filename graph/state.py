from typing import TypedDict, Any

class StudyPlannerState(TypedDict, total=False):
    action: str
    subjects: list[dict[str, Any]]
    pending_topics: list[dict[str, Any]]
    daily_hours: int
    start_time: str
    planning_days: int
    today: str
    priority_summary: str
    sessions: list[dict[str, Any]]
    message: str
    needs_revision: bool
