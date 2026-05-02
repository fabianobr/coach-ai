from coach.llm import Message


class SessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, list[Message]] = {}

    def get_or_create(self, session_id: str) -> list[Message]:
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        return self.sessions[session_id]

    def append(self, session_id: str, message: Message) -> None:
        self.get_or_create(session_id).append(message)

    def clear(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
