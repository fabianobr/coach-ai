import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime

from coach.llm import Message
from coach.logger import ExerciseResult

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    user_id: int
    messages: list[Message] = field(default_factory=list)
    current_day: str = "D1"
    exercises: list[ExerciseResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class UserSessionStore:
    def __init__(self, max_sessions: int = 5000) -> None:
        self.sessions: OrderedDict[int, UserSession] = OrderedDict()
        self.max_sessions = max_sessions

    def get_or_create(self, user_id: int) -> UserSession:
        if user_id not in self.sessions:
            if len(self.sessions) >= self.max_sessions:
                evicted_id = self.sessions.popitem(last=False)[0]
                logger.warning(f"Evicted oldest user session {evicted_id} at capacity {self.max_sessions}")
            self.sessions[user_id] = UserSession(user_id=user_id)
        else:
            self.sessions.move_to_end(user_id)
        return self.sessions[user_id]

    def clear(self, user_id: int) -> None:
        self.sessions.pop(user_id, None)
