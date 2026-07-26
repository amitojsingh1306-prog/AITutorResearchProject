"""Central orchestrator for information diffusion between tutor agents."""

import logging

from backend.agents.conversation_state_agent import ConversationStateAgent
from backend.agents.dialogue_manager_agent import DialogueManagerAgent
from backend.agents.intent_agent import IntentAgent
from backend.agents.knowledge_agent import KnowledgeAgent
from backend.agents.memory_agent import MemoryAgent
from backend.agents.reflection_agent import ReflectionAgent
from backend.agents.response_generation_agent import ResponseGenerationAgent
from backend.agents.teaching_planner_agent import TeachingPlannerAgent
from backend.database.chroma_repository import ChromaChatRepository
from backend.llm.groq_client import GroqClient
from backend.models.chat import Message
from backend.models.learner import OrchestratedContext


logger = logging.getLogger(__name__)


class TutorOrchestrator:
    """Coordinate specialized agents through progressive information diffusion."""

    def __init__(
        self,
        repository: ChromaChatRepository,
        llm_client: GroqClient | None = None,
    ) -> None:
        self._repository = repository
        self._llm_client = llm_client
        self._intent_agent = IntentAgent()
        self._conversation_state_agent = ConversationStateAgent()
        self._memory_agent = MemoryAgent(repository)
        self._knowledge_agent = KnowledgeAgent()
        self._reflection_agent = ReflectionAgent(repository)
        self._teaching_planner_agent = TeachingPlannerAgent()
        self._dialogue_manager_agent = DialogueManagerAgent()
        self._response_generation_agent = ResponseGenerationAgent()
        self._last_context: OrchestratedContext | None = None

    def generate_reply(self, chat_id: str, user_message: Message) -> str:
        context = self._build_context(user_message)
        self._last_context = context

        if self._should_use_controlled_reply(context):
            return self._response_generation_agent.fallback_reply(context)

        if self._llm_client is None:
            return self._response_generation_agent.fallback_reply(context)

        messages = self._repository.list_messages(chat_id, user_message.user_id)
        if not messages or messages[-1].id != user_message.id:
            messages.append(user_message)
        return self._llm_client.generate_reply(
            self._response_generation_agent.select_messages(messages),
            system_prompt=self._response_generation_agent.system_prompt(context),
        )

    def record_assistant_reply(self, assistant_message: Message) -> None:
        if self._last_context is None:
            return
        if self._last_context.plan.mode == "acknowledge":
            return
        self._memory_agent.store_assistant_experience(
            assistant_message=assistant_message,
            topic=self._last_context.knowledge.topic,
        )

    @staticmethod
    def _should_use_controlled_reply(context: OrchestratedContext) -> bool:
        return context.dialogue.conversation_type in {
            "gratitude",
            "goodbye",
            "greeting",
            "excitement",
            "casual_chat",
            "confusion",
            "understanding",
            "correction",
            "disagreement",
        }

    def _build_context(self, user_message: Message) -> OrchestratedContext:
        intent = self._intent_agent.analyze(user_message.content)
        self._log_agent("Intent Agent", {"content": user_message.content}, intent)

        conversation_state = self._conversation_state_agent.classify(intent)
        self._log_agent("Conversation State Agent", intent, conversation_state)

        memory = self._memory_agent.process(
            user_message=user_message,
            intent=intent,
            conversation_state=conversation_state,
        )
        self._log_agent("Memory Agent", conversation_state, memory)

        knowledge = self._knowledge_agent.enrich(
            intent=intent,
            conversation_state=conversation_state,
            memory=memory,
        )
        self._log_agent("Knowledge Agent", memory, knowledge)

        reflection = self._reflection_agent.reflect(user_message.user_id, memory)
        self._log_agent("Reflection Agent", memory, reflection)

        plan = self._teaching_planner_agent.plan(
            conversation_state=conversation_state,
            memory=memory,
            knowledge=knowledge,
            reflection=reflection,
        )
        self._log_agent("Teaching Planner Agent", reflection, plan)

        dialogue = self._dialogue_manager_agent.calibrate(
            intent=intent,
            conversation_state=conversation_state,
            plan=plan,
        )
        self._log_agent("Dialogue Manager", plan, dialogue)

        context = OrchestratedContext(
            intent=intent,
            conversation_state=conversation_state,
            memory=memory,
            knowledge=knowledge,
            reflection=reflection,
            plan=plan,
            dialogue=dialogue,
        )
        self._log_agent("Response Generation Agent", dialogue, context)
        return context

    def _log_agent(self, name: str, agent_input: object, agent_output: object) -> None:
        logger.info(
            "%s input=%s output=%s",
            name,
            self._jsonish(agent_input),
            self._jsonish(agent_output),
        )

    @staticmethod
    def _jsonish(value: object) -> str:
        if hasattr(value, "model_dump_json"):
            return value.model_dump_json()  # type: ignore[no-any-return]
        return str(value)
