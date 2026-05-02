from collections import OrderedDict

from coach.llm import Message


class SessionStore:
    def __init__(self, max_sessions: int = 1000) -> None:
        self.sessions: OrderedDict[str, list[Message]] = OrderedDict()
        self.max_sessions = max_sessions

    def get_or_create(self, session_id: str) -> list[Message]:
        if session_id not in self.sessions:
            if len(self.sessions) >= self.max_sessions:
                self.sessions.popitem(last=False)
            self.sessions[session_id] = []
        else:
            self.sessions.move_to_end(session_id)
        return self.sessions[session_id]

    def append(self, session_id: str, message: Message) -> None:
        self.get_or_create(session_id).append(message)

    def clear(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
