from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ConversationTurn:
    role: Literal["user", "assistant"]
    text: str


@dataclass
class ConversationSession:
    chat_id: int
    history: list[ConversationTurn] = field(default_factory=list)

    def append(self, role: Literal["user", "assistant"], text: str) -> None:
        self.history.append(ConversationTurn(role=role, text=text))

    def recent_history(self, max_turns: int = 6) -> str:
        turns = self.history[-max_turns:]
        if not turns:
            return "(no prior turns)"
        lines = []
        for turn in turns:
            label = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{label}: {turn.text.strip()}")
        return "\n".join(lines)


class ConversationManager:
    def __init__(self) -> None:
        self._sessions: dict[int, ConversationSession] = {}

    def get(self, chat_id: int) -> ConversationSession | None:
        return self._sessions.get(chat_id)

    def set(self, session: ConversationSession) -> None:
        self._sessions[session.chat_id] = session

    def clear(self, chat_id: int) -> None:
        self._sessions.pop(chat_id, None)

    def has(self, chat_id: int) -> bool:
        return chat_id in self._sessions
