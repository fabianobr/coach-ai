import asyncio
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
    current_day: str | None = None
    exercises: list[ExerciseResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class UserSessionStore:
    def __init__(self, max_sessions: int = 5000) -> None:
        self.sessions: OrderedDict[int, UserSession] = OrderedDict()
        self.locks: OrderedDict[int, asyncio.Lock] = OrderedDict()
        self.max_sessions = max_sessions

    def get_or_create(self, user_id: int) -> UserSession:
        if user_id not in self.sessions:
            if len(self.sessions) >= self.max_sessions:
                evicted_id = self.sessions.popitem(last=False)[0]
                self.locks.pop(evicted_id, None)
                logger.warning(f"Evicted oldest user session {evicted_id} at capacity {self.max_sessions}")
            self.sessions[user_id] = UserSession(user_id=user_id)
            self.locks[user_id] = asyncio.Lock()
        else:
            self.sessions.move_to_end(user_id)
        return self.sessions[user_id]

    def get_lock(self, user_id: int) -> asyncio.Lock:
        """Get the asyncio lock for a user. Creates session if needed."""
        if user_id not in self.locks:
            self.get_or_create(user_id)
        return self.locks[user_id]

    def clear(self, user_id: int) -> None:
        self.sessions.pop(user_id, None)
        self.locks.pop(user_id, None)
