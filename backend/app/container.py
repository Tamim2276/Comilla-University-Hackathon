"""Composition root (AR-05): the ONLY place that builds adapters and hands them to use cases.

Everything is built lazily on first use and then reused, so a missing model or service only
breaks the feature that needs it, not the whole app. Later steps add adapters and use cases here.
"""

import logging
from functools import cached_property

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.application.ports.engine import AnswerEngine
from app.application.ports.llm import LLM
from app.application.ports.repositories import (
    AnswerCache,
    CallRepo,
    ChecklistRepo,
    ClusterRepo,
    ConversationRepo,
    QuestionLogRepo,
)
from app.application.use_cases.ask_question import AskQuestion
from app.application.use_cases.history import DeleteHistory, GetHistory
from app.application.use_cases.services import ListServices
from app.config import Settings
from app.domain.entities import Service
from app.infrastructure.agent.stub_engine import StubAnswerEngine
from app.infrastructure.cache.answer_cache import SqlAnswerCache
from app.infrastructure.catalog.yaml_services import load_services
from app.infrastructure.db.repositories import (
    SqlCallRepo,
    SqlChecklistRepo,
    SqlClusterRepo,
    SqlConversationRepo,
    SqlQuestionLogRepo,
)
from app.infrastructure.db.session import init_db, make_engine, make_session_factory
from app.infrastructure.llm.gemini_llm import GeminiLLM
from app.infrastructure.llm.ollama_llm import OllamaLLM
from app.infrastructure.llm.routed_llm import RoutedLLM
from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever
from app.infrastructure.retrieval.e5_embedder import E5Embedder

log = logging.getLogger(__name__)

NOT_CONFIGURED = "not_configured"
EMPTY = "empty"


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ------------------------------------------------------------ database

    @cached_property
    def engine(self) -> Engine:
        return make_engine(self.settings.database_url)

    @cached_property
    def session_factory(self) -> sessionmaker[Session]:
        return make_session_factory(self.engine)

    def init_database(self) -> None:
        init_db(self.engine)

    # ------------------------------------------------------------ repositories (ports -> SQL adapters)

    @cached_property
    def conversations(self) -> ConversationRepo:
        return SqlConversationRepo(self.session_factory)

    @cached_property
    def checklists(self) -> ChecklistRepo:
        return SqlChecklistRepo(self.session_factory)

    @cached_property
    def question_logs(self) -> QuestionLogRepo:
        return SqlQuestionLogRepo(self.session_factory)

    @cached_property
    def calls(self) -> CallRepo:
        return SqlCallRepo(self.session_factory)

    @cached_property
    def clusters(self) -> ClusterRepo:
        return SqlClusterRepo(self.session_factory)

    @cached_property
    def answer_cache(self) -> AnswerCache:
        return SqlAnswerCache(self.session_factory)

    # ------------------------------------------------------------ service catalog

    @cached_property
    def services(self) -> list[Service]:
        return load_services(self.settings.services_file)

    # ------------------------------------------------------------ retrieval (FR-AGT-05)

    @cached_property
    def embedder(self) -> E5Embedder:
        # The model loads on first use, not here.
        return E5Embedder(self.settings.embed_model, self.settings.embed_cache_dir)

    @cached_property
    def retriever(self) -> ChromaRetriever:
        return ChromaRetriever(
            self.settings.chroma_dir,
            self.embedder,
            min_score=self.settings.retrieval_min_score,
        )

    # ------------------------------------------------------------ LLM (FR-AGT-16, FR-AGT-18)

    @cached_property
    def gemini(self) -> GeminiLLM:
        s = self.settings
        return GeminiLLM(s.gemini_key_list, s.gemini_model_main, s.gemini_model_fast)

    @cached_property
    def ollama(self) -> OllamaLLM:
        return OllamaLLM(self.settings.ollama_url, self.settings.ollama_model)

    @cached_property
    def llm(self) -> LLM:
        """LLM_BACKEND: gemini | ollama | hybrid (FAST on Ollama, MAIN on Gemini with Ollama fallback)."""
        backend = self.settings.llm_backend
        if backend == "ollama":
            return self.ollama
        if backend == "hybrid":
            return RoutedLLM(main=self.gemini, local=self.ollama)
        return self.gemini

    def check_llm(self) -> str:
        if self.settings.llm_backend == "gemini" and not self.gemini.configured:
            return NOT_CONFIGURED
        try:
            return "ok" if self.llm.check() else "error"
        except Exception:
            log.exception("LLM health check failed")
            return "error"

    # ------------------------------------------------------------ agent

    @cached_property
    def answer_engine(self) -> AnswerEngine:
        return StubAnswerEngine()  # replaced by the LangGraph agent in D1-T4

    # ------------------------------------------------------------ use cases

    @cached_property
    def list_services(self) -> ListServices:
        return ListServices(self.services)

    @cached_property
    def ask_question(self) -> AskQuestion:
        return AskQuestion(
            engine=self.answer_engine,
            conversations=self.conversations,
            checklists=self.checklists,
            question_logs=self.question_logs,
            services=self.services,
            phone_hash_salt=self.settings.phone_hash_salt.get_secret_value(),
        )

    @cached_property
    def get_history(self) -> GetHistory:
        return GetHistory(self.conversations, self.checklists)

    @cached_property
    def delete_history(self) -> DeleteHistory:
        return DeleteHistory(self.conversations, self.checklists)

    # ============================================================ team areas (docs/BUILD_PLAN.md Section 0.4)
    # Add new adapters and use cases ONLY inside your own area below, so two pull requests never
    # change the same lines. Changing a line outside your area: agree with its owner first.

    # ------------------------------------------------------------ voice area
    # Planned here: call_placer (Twilio), tts (gTTS), start_callback, handle_call_end, synthesize_speech
    # (steps D1-A3, D1-A5, D2-A1, D2-R2, D2-A2).

    # ------------------------------------------------------------ SMS, background and admin area
    # Planned here: sms (console | textbee), runner (ThreadPoolRunner), admin use cases
    # (steps D1-A4, D2-R1). D1-A4 also passes sms + runner into ask_question above.

    # ------------------------------------------------------------ AI area
    # Planned here: classifier (tfidf | banglabert | llm), the LangGraph engine (replaces answer_engine
    # above), clusterer and cluster use cases (steps D1-R4, D1-T4, D1-T5, D2-T1, D2-T2, D2-T4).

    # ------------------------------------------------------------ health (NFR-REL-02)

    def check_db(self) -> str:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return "ok"
        except Exception:  # any failure means "not usable"; details go to the log
            log.exception("database health check failed")
            return "error"

    def check_vector_db(self) -> str:
        """ok = passages are stored; empty = run `python -m scripts.ingest`. Never loads the model."""
        if not self.settings.chroma_dir.exists():
            return EMPTY  # do not create the folder just by asking
        try:
            return "ok" if self.retriever.count() > 0 else EMPTY
        except Exception:
            log.exception("vector store health check failed")
            return "error"

    def health(self) -> dict[str, str]:
        """Status of each part. The router reports not_configured until it is built."""
        parts = {
            "db": self.check_db(),
            "llm": self.check_llm(),
            "vector_db": self.check_vector_db(),
            "router": NOT_CONFIGURED,
        }
        parts["status"] = "ok" if parts["db"] == "ok" else "error"
        return parts

    # ------------------------------------------------------------ shutdown

    def close(self) -> None:
        if "engine" in self.__dict__:  # only if it was ever built
            self.engine.dispose()
        if "ollama" in self.__dict__:
            self.ollama.close()
