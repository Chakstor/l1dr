from pydantic import BaseModel, Field

class ProjectMetadata(BaseModel):
    project_name: str | None = None
    assumed_team_size: int | None = None
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = None
    explicit_constraints: list[str] = Field(default_factory=list)
    rejected_options: list[str] = Field(default_factory=list)

class Message(BaseModel):
    role: str
    content: str

MAX_TURNS = 6

class ConversationHistory(BaseModel):
    messages: list[Message] = Field(default_factory=list)

    def add_turn(self,user_message: str, assistant_message: str):
        self.messages.append(
            Message(role="user", content=user_message)
        )
        self.messages.append(
            Message(role="assistant", content=assistant_message)
        )

        max_messages = MAX_TURNS * 2

        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]


from uuid import uuid4

class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    history: ConversationHistory = Field(default_factory=ConversationHistory)
    project_metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)

# Las sesiones se almacenan en memoria
sessions: dict[str, Session] = {}