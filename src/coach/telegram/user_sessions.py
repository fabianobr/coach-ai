from dataclasses import dataclass, field
from datetime import datetime

from coach.llm import Message


@dataclass
class UserSession:
    user_id: int
    messages: list[Message] = field(default_factory=list)
    current_day: str = "D1"
    created_at: datetime = field(default_factory=datetime.now)


class UserSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[int, UserSession] = {}

    def get_or_create(self, user_id: int) -> UserSession:
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id=user_id)
        return self.sessions[user_id]

    def clear(self, user_id: int) -> None:
        self.sessions.pop(user_id, None)
