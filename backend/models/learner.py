"""Learner memory and orchestration schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.models.chat import Message


class LearnerProfile(BaseModel):
    """Long-term profile used to personalize future tutoring turns."""

    user_id: str
    name: str | None = None
    email: str | None = None
    field_of_study: str | None = None
    onboarding_complete: bool = False
    learning_goals: list[str] = Field(default_factory=list)
    completed_topics: list[str] = Field(default_factory=list)
    current_topics: list[str] = Field(default_factory=list)
    preferred_explanation_style: str | None = None
    skill_level: str = "beginner"
    previous_mistakes: list[str] = Field(default_factory=list)
    ongoing_projects: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)


class MemoryRecord(BaseModel):
    """A durable learner memory stored separately from chat messages."""

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


class StudentMemoryObject(BaseModel):
    """Structured A-MEM-style student memory stored inside MemoryRecord.memory."""

    topic: str | None = None
    concepts: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    progress: str | None = None
    important_facts: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    timestamp: datetime


class MemoryDecision(BaseModel):
    """Mem0-style operation selected for one learner turn."""

    action: str = "NOOP"
    category: str | None = None
    memory: str | None = None
    target_memory_id: str | None = None
    reason: str = ""


class RetrievedMemory(BaseModel):
    """Memory returned by recency + importance + relevance retrieval."""

    record: MemoryRecord
    recency_score: float
    importance_score: float
    relevance_score: float
    total_score: float


class MemoryContextItem(BaseModel):
    """Prompt-safe retrieved memory context for response grounding."""

    type: str
    content: str
    topic: str | None = None
    score: float | None = None


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
    decision: MemoryDecision = Field(default_factory=MemoryDecision)
    stored_memories: list[MemoryRecord] = Field(default_factory=list)
    retrieved_memories: list[RetrievedMemory] = Field(default_factory=list)
    memories: list[MemoryRecord] = Field(default_factory=list)
    working_messages: list[Message] = Field(default_factory=list)


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
    memory_context: list[MemoryContextItem] = Field(default_factory=list)
    knowledge: KnowledgeSignal
    reflection: ReflectionSignal
    plan: TeachingPlan
    dialogue: DialogueSignal
