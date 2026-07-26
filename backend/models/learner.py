"""Learner memory and orchestration schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class LearnerProfile(BaseModel):
    """Long-term profile used to personalize future tutoring turns."""

    user_id: str
    learning_goals: list[str] = Field(default_factory=list)
    completed_topics: list[str] = Field(default_factory=list)
    current_topics: list[str] = Field(default_factory=list)
    preferred_explanation_style: str | None = None
    skill_level: str = "beginner"
    previous_mistakes: list[str] = Field(default_factory=list)
    ongoing_projects: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)


class MemoryRecord(BaseModel):
    """A meaningful learner experience stored in the memory stream."""

    id: str
    user_id: str
    timestamp: datetime
    memory: str
    importance: int = Field(ge=1, le=10)
    type: str
    topic: str | None = None
    status: str = "active"
    source_message_id: str | None = None
    embedding: list[float] = Field(default_factory=list)


class RetrievedMemory(BaseModel):
    """Memory returned by recency + importance + relevance retrieval."""

    record: MemoryRecord
    recency_score: float
    importance_score: float
    relevance_score: float
    total_score: float


class IntentSignal(BaseModel):
    """Structured JSON output from the Intent Agent."""

    action: str
    topic: str | None = None
    raw_text: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ConversationStateSignal(BaseModel):
    """Structured JSON output from the Conversation State Agent."""

    state: str
    reaction_type: str
    reason: str


class MemorySignal(BaseModel):
    """Structured JSON output from the Memory Agent."""

    profile: LearnerProfile
    stored_memories: list[MemoryRecord] = Field(default_factory=list)
    retrieved_memories: list[RetrievedMemory] = Field(default_factory=list)


class KnowledgeSignal(BaseModel):
    """Structured JSON output from the Knowledge Agent."""

    topic: str
    framing: str
    prerequisites: list[str] = Field(default_factory=list)
    avoid_repeating: list[str] = Field(default_factory=list)
    knowledge_notes: list[str] = Field(default_factory=list)


class ReflectionSignal(BaseModel):
    """Structured JSON output from the Reflection Agent."""

    triggered: bool
    insights: list[MemoryRecord] = Field(default_factory=list)
    reason: str


class TeachingPlan(BaseModel):
    """Structured JSON output from the Teaching Planner Agent."""

    mode: str
    review: bool
    depth: str
    steps: list[str] = Field(default_factory=list)
    next_action: str
    tone: str


class DialogueSignal(BaseModel):
    """Structured JSON output from the Dialogue Manager."""

    conversation_type: str
    tone: str
    length: str
    style: str
    acknowledgement: str
    ask_follow_up: bool
    stop_after_acknowledgement: bool
    avoid_openings: list[str] = Field(default_factory=list)
    response_rules: list[str] = Field(default_factory=list)


class OrchestratedContext(BaseModel):
    """Full information-diffusion trace for one tutor turn."""

    intent: IntentSignal
    conversation_state: ConversationStateSignal
    memory: MemorySignal
    knowledge: KnowledgeSignal
    reflection: ReflectionSignal
    plan: TeachingPlan
    dialogue: DialogueSignal
