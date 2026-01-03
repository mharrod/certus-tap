# Conversational Interface with Memory for Certus

**Status:** Draft v1.0
**Author:** System Architecture
**Date:** 2025-12-11
## Executive Summary

While the **AAIF Agent Framework** provides infrastructure for AI agents and the **Security SLM** optimizes cost/performance for security tasks, users currently interact with these capabilities through **fragmented interfaces** (CLI, API, IDE plugins). This proposal defines a **unified conversational interface** that serves as the "front door" to Certus' AI/agent ecosystem, providing natural language interaction with **multi-turn conversation memory**, **intelligent routing**, and **personalized assistance**.

**The Problem:**

Current interaction model forces users to:
- Know which tool to use (Goose CLI? MCP? N8n? Direct API?)
- Understand technical details (MCP server names, API endpoints)
- Repeat context in every interaction (no conversation memory)
- Switch between multiple interfaces for related tasks
- Lack personalization (system doesn't learn user preferences)

**The Solution:**

A **conversational interface powered by Haystack AI** that:
- Provides **natural language** interaction with all Certus capabilities
- Maintains **conversation memory** (short-term, long-term, organizational)
- **Intelligently routes** queries to optimal backends (SLM, AAIF agents, Certus services)
- Offers **personalized recommendations** based on user history and preferences
- Enables **proactive assistance** (notifications, suggestions, automation)
- Supports **team collaboration** (shared context, handoffs)

**Strategic Positioning:**

```
┌─────────────────────────────────────────────────────────────────┐
│           Certus AI-Powered Security Platform                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  👤 User Experience Layer (THIS PROPOSAL)                      │
│  ┌───────────────────────────────────────────────────────┐    │
│  │  💬 Certus Chat - Conversational Interface            │    │
│  │  ├─ Natural language conversations                    │    │
│  │  ├─ Multi-turn dialogue with memory                   │    │
│  │  ├─ Personalized recommendations                      │    │
│  │  ├─ Proactive assistance                              │    │
│  │  └─ Team collaboration                                │    │
│  └───────────────────────────────────────────────────────┘    │
│                           ↓↓↓                                   │
│  🧠 Intelligence Routing Layer (Haystack Pipelines)            │
│  ┌───────────────────────────────────────────────────────┐    │
│  │  Query Classification & Routing                       │    │
│  │  ├─ Knowledge questions → Certus-Ask (RAG)           │    │
│  │  ├─ Quick classification → Security SLM               │    │
│  │  ├─ Complex workflows → Goose agents (AAIF)          │    │
│  │  ├─ Data queries → Certus-Insight                     │    │
│  │  └─ Complex reasoning → GPT-4                         │    │
│  └───────────────────────────────────────────────────────┘    │
│                           ↓↓↓                                   │
│  🤖 Execution Layer (from AAIF + SLM proposals)                │
│  ├─ AAIF Agents (Goose, MCP, AGENTS.md)                       │
│  ├─ Security SLM (fast triage, classification)                │
│  └─ Large LLMs (GPT-4, Claude for complex reasoning)          │
│                           ↓↓↓                                   │
│  🔌 Data/Services Layer                                        │
│  └─ Certus Services (Assurance, Trust, Insight, Ask, etc.)    │
└─────────────────────────────────────────────────────────────────┘
```

**What This Enables:**

1. **Unified Interface** - One conversational interface for all Certus AI capabilities (no tool fragmentation)
2. **Conversation Memory** - Multi-turn dialogues with context retention (short-term, long-term, organizational)
3. **Intelligent Routing** - Automatically route to optimal backend based on query type and cost/latency tradeoffs
4. **Personalization** - Learn user preferences, priorities, and patterns over time
5. **Proactive Assistance** - System suggests actions, sends notifications, automates routine tasks
6. **Team Collaboration** - Share context, collaborate on security tasks, handoff conversations
7. **Seamless Integration** - Leverages existing Haystack + OpenSearch infrastructure

**Business Impact:**

- **Productivity:** 50%+ faster for common security tasks (no tool switching, context retention)
- **Adoption:** Lower barrier to entry (natural language vs. CLI/API knowledge)
- **Collaboration:** Teams share security context automatically
- **Insights:** Analyze conversation patterns to improve workflows
- **Cost Efficiency:** Intelligent routing minimizes expensive LLM calls

This proposal completes the three-part AI/agent strategy:
1. **AAIF Proposal** - Agent infrastructure (how agents work)
2. **SLM Proposal** - Cost/performance optimization (fast security tasks)
3. **Conversational Interface** - User experience (how humans interact) ← **THIS PROPOSAL**

## Motivation

### Current State

**Existing Interaction Models:**

```
Developer wants to check security:

Option 1: Goose CLI
$ goose --profile certus-security
🦆 User: Scan my repo
→ Requires: CLI knowledge, profile configuration

Option 2: MCP via IDE
[In VS Code, trigger MCP command]
→ Requires: IDE extension, MCP understanding

Option 3: N8n Workflow
[Configure workflow in N8n UI]
→ Requires: Workflow knowledge, manual setup

Option 4: Direct API
$ curl -X POST /api/scans -d '{"repo": "..."}'
→ Requires: API knowledge, authentication setup

Option 5: Certus-Ask (Q&A only)
Ask a question → Get an answer (no workflows)
→ Limited to knowledge retrieval
```

**Problems with Current Approach:**

1. **Fragmentation** - Users must know which tool to use for what
2. **No Memory** - Each interaction starts from scratch, context is lost
3. **Technical Barrier** - Requires understanding of CLI, MCP, APIs
4. **No Personalization** - System doesn't learn user preferences
5. **Inefficient** - Users repeat the same information across interactions
6. **Limited Collaboration** - Hard to share security context with team

### What Users Want

**Ideal Interaction Model:**

```
User → Chat interface (web/mobile/Slack)
  ↓
Natural language: "Check if my repo has any critical vulnerabilities"
  ↓
System:
  - Remembers which repo user typically works on
  - Knows user's priority is authentication issues
  - Routes to Security SLM for fast triage
  - Uses Goose agent for detailed analysis if needed
  - Stores conversation for future reference
  ↓
Response: "I scanned api-server (your main repo). Found 2 critical issues,
both auth-related (your priority). Should I create a fix plan?"
  ↓
User: "Yes"
  ↓
System: [Remembers context, executes workflow]
```

**Key Requirements:**

| Requirement | Current State | Desired State |
|-------------|---------------|---------------|
| **Interface** | CLI, API, IDE plugins | Single chat interface |
| **Memory** | None (stateless) | Multi-turn with context |
| **Routing** | User chooses tool | Automatic, intelligent |
| **Personalization** | None | Learns preferences |
| **Collaboration** | Manual sharing | Automatic context sharing |
| **Accessibility** | Technical users only | All team members |

### Why Conversation + Memory?

#### 1. Natural Interaction

Humans think conversationally, not in API calls:

```
❌ Technical:
$ certus-agent --profile=security scan --repo=api-server --profile=heavy --format=sarif

✅ Conversational:
"Scan api-server for vulnerabilities"
```

#### 2. Context Retention

Critical for security work which spans multiple sessions:

```
Monday:
User: "We need to prepare for SOC2 audit next month"
System: "Noted. I'll track your compliance posture."

Wednesday:
User: "Run a scan on payment-service"
System: "Scan complete. I found 3 compliance gaps relevant to
       your SOC2 audit (mentioned Monday). Should I prioritize these?"
```

#### 3. Learning & Personalization

System learns user patterns:

```
After 2 weeks:
- User always scans after PRs → System proactively suggests scans
- User prioritizes auth issues → System highlights auth findings first
- User prefers detailed reports → System provides more context
```

#### 4. Team Collaboration

Security work is collaborative:

```
Developer: "I'm working on fixing the SQL injection in auth.py"
System: "I see Sarah started this yesterday. Here's her analysis..."

Security Team: "What's the status on auth.py fix?"
System: "Developer started fix 2 hours ago. Here's the conversation..."
```

### Problems Addressed

| Problem | Impact | Solution |
|---------|--------|----------|
| **Tool fragmentation** | Users waste time figuring out which tool to use | Single conversational interface |
| **No context retention** | Users repeat information, slower workflows | Multi-level memory (short/long/org) |
| **Technical barrier** | Low adoption, only power users benefit | Natural language, accessible to all |
| **No personalization** | Generic experience, inefficient | Learn preferences, priorities, patterns |
| **Isolated interactions** | No collaboration, duplicate work | Shared team context, handoffs |
| **Reactive only** | Users must initiate everything | Proactive suggestions, notifications |

## Goals & Non-Goals

| Goals | Non-Goals |
|-------|-----------|
| Build conversational interface for all Certus AI capabilities | Replace existing interfaces (CLI, API, IDE plugins remain) |
| Implement multi-level memory (short-term, long-term, organizational) | Store all conversation data indefinitely (implement retention policies) |
| Intelligent routing to optimal backends (SLM, AAIF, Certus services) | Build another agent framework (use AAIF infrastructure) |
| Leverage existing Haystack + OpenSearch infrastructure | Replace Haystack or OpenSearch (use what we have) |
| Personalization based on user history and preferences | Require users to manually configure every preference |
| Enable team collaboration with shared context | Build a full collaboration platform (focus on security context) |
| Proactive assistance (notifications, suggestions) | Fully autonomous operations without user approval |
| Support web, mobile, and messaging platforms (Slack, Teams) | Build custom mobile apps from scratch (use web for mobile initially) |

## Proposed Solution

### Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│              Certus Conversational Interface Architecture             │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Frontend Layer                                 │    │
│  │                                                             │    │
│  │  Web App (React + TypeScript)                              │    │
│  │  ├─ Chat UI with real-time updates (WebSocket)            │    │
│  │  ├─ Conversation history browser                           │    │
│  │  ├─ Code snippet rendering                                 │    │
│  │  └─ Visualization (charts, graphs)                         │    │
│  │                                                             │    │
│  │  Mobile Web (Responsive)                                    │    │
│  │  └─ Same React app, mobile-optimized                       │    │
│  │                                                             │    │
│  │  Messaging Integrations (Phase 2+)                         │    │
│  │  ├─ Slack bot                                              │    │
│  │  ├─ Microsoft Teams bot                                    │    │
│  │  └─ Discord bot                                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↕                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              API Layer (FastAPI)                            │    │
│  │                                                             │    │
│  │  WebSocket Server                                           │    │
│  │  ├─ Real-time chat streaming                               │    │
│  │  ├─ Session management                                     │    │
│  │  └─ Presence tracking                                       │    │
│  │                                                             │    │
│  │  REST API                                                   │    │
│  │  ├─ /chat/message (send message)                           │    │
│  │  ├─ /chat/history (get conversation)                       │    │
│  │  ├─ /chat/sessions (list sessions)                         │    │
│  │  └─ /chat/search (semantic search)                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↕                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Haystack Pipeline Layer                        │    │
│  │                                                             │    │
│  │  Main Chat Pipeline                                         │    │
│  │  ├─ MemoryRetriever (load context from OpenSearch)        │    │
│  │  ├─ QueryClassifier (classify query type)                  │    │
│  │  ├─ IntelligentRouter (route to backend)                   │    │
│  │  └─ ResponseGenerator (format response)                    │    │
│  │                                                             │    │
│  │  Backend Pipelines                                          │    │
│  │  ├─ RAG Pipeline (knowledge questions)                     │    │
│  │  ├─ SLM Pipeline (fast security classification)            │    │
│  │  ├─ Agent Pipeline (complex workflows via AAIF)           │    │
│  │  └─ Data Pipeline (Certus service queries)                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↕                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Memory Layer                                   │    │
│  │                                                             │    │
│  │  OpenSearch (Existing Infrastructure) ✅                   │    │
│  │  ├─ Conversation embeddings (vector search)                │    │
│  │  ├─ Semantic search over history                           │    │
│  │  └─ Full-text search (hybrid search)                       │    │
│  │                                                             │    │
│  │  PostgreSQL                                                 │    │
│  │  ├─ Conversation metadata (users, sessions)                │    │
│  │  ├─ Message history (structured data)                      │    │
│  │  ├─ User preferences                                       │    │
│  │  └─ Team/org settings                                      │    │
│  │                                                             │    │
│  │  Redis                                                      │    │
│  │  ├─ Active session state                                   │    │
│  │  ├─ Rate limiting                                          │    │
│  │  └─ Cache (embeddings, responses)                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↕                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Integration Layer                              │    │
│  │                                                             │    │
│  │  Backend Connectors                                         │    │
│  │  ├─ Security SLM Client                                    │    │
│  │  ├─ Goose Agent SDK (AAIF)                                 │    │
│  │  ├─ MCP Client (call Certus MCP servers)                   │    │
│  │  ├─ Certus API Clients (Assurance, Trust, Insight, Ask)   │    │
│  │  └─ LLM Clients (OpenAI, Anthropic)                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Haystack Pipeline Architecture

**Main Chat Pipeline:**

```python
# certus_chat/pipelines/main_chat.py
from haystack import Pipeline, component
from haystack.document_stores.opensearch import OpenSearchDocumentStore
from haystack.components.retrievers import OpenSearchEmbeddingRetriever
from haystack.components.embedders import SentenceTransformersTextEmbedder

@component
class ConversationMemoryRetriever:
    """
    Retrieve conversation context from OpenSearch.

    Loads:
    - Recent messages from current session (short-term memory)
    - Relevant past conversations (long-term memory via semantic search)
    - User preferences and patterns
    """

    def __init__(
        self,
        document_store: OpenSearchDocumentStore,
        db_client  # PostgreSQL client for structured data
    ):
        self.document_store = document_store
        self.db = db_client
        self.embedder = SentenceTransformersTextEmbedder(
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.retriever = OpenSearchEmbeddingRetriever(
            document_store=document_store
        )

    @component.output_types(
        recent_messages=list,
        relevant_history=list,
        user_context=dict
    )
    async def run(
        self,
        query: str,
        user_id: str,
        session_id: str,
        top_k: int = 5
    ):
        """Retrieve all relevant context for the query."""

        # 1. Get recent messages from current session (PostgreSQL)
        recent = await self.db.fetch("""
            SELECT id, role, content, timestamp, metadata
            FROM messages
            WHERE session_id = $1
            ORDER BY timestamp DESC
            LIMIT 10
        """, session_id)

        # 2. Semantic search over all past conversations (OpenSearch)
        query_embedding = self.embedder.run(query)["embedding"]

        relevant = await self.retriever.run(
            query_embedding=query_embedding,
            filters={
                "user_id": user_id,
                "session_id": {"$ne": session_id}  # Exclude current session
            },
            top_k=top_k
        )

        # 3. Load user preferences and context
        user_context = await self.db.fetchrow("""
            SELECT preferences, priorities, repositories, team_id
            FROM users
            WHERE id = $1
        """, user_id)

        return {
            "recent_messages": list(reversed(recent)),  # Chronological order
            "relevant_history": relevant["documents"],
            "user_context": dict(user_context) if user_context else {}
        }

@component
class QueryClassifier:
    """
    Classify query type to determine routing.

    Types:
    - knowledge_question: Factual questions (What is CVE-X?)
    - code_analysis: Code security checks
    - workflow_execution: Multi-step tasks (scan, fix, deploy)
    - data_query: Query Certus data (show me trends)
    - general_conversation: Chitchat, clarifications
    """

    @component.output_types(query_type=str, confidence=float)
    async def run(self, query: str, context: dict):
        """Classify query using lightweight model or rules."""

        query_lower = query.lower()

        # Rule-based classification (fast)
        # Can be replaced with SLM classifier for better accuracy

        if any(word in query_lower for word in ["what is", "explain", "tell me about"]):
            return {"query_type": "knowledge_question", "confidence": 0.9}

        elif any(word in query_lower for word in ["scan", "check", "analyze", "fix", "remediate"]):
            return {"query_type": "workflow_execution", "confidence": 0.85}

        elif any(word in query_lower for word in ["show", "trends", "metrics", "report"]):
            return {"query_type": "data_query", "confidence": 0.8}

        elif "code" in context.get("attachments", []):
            return {"query_type": "code_analysis", "confidence": 0.95}

        else:
            return {"query_type": "general_conversation", "confidence": 0.6}

@component
class IntelligentRouter:
    """
    Route queries to optimal backend based on type, cost, latency.

    Routing decisions:
    - knowledge_question → Certus-Ask (RAG)
    - code_analysis (simple) → Security SLM
    - code_analysis (complex) → Security SLM + GPT-4
    - workflow_execution → Goose agent (AAIF)
    - data_query → Certus-Insight API
    """

    def __init__(self, slm_client, goose_client, certus_ask_client, insight_client):
        self.slm = slm_client
        self.goose = goose_client
        self.certus_ask = certus_ask_client
        self.insight = insight_client

    @component.output_types(response=str, backend_used=str, metadata=dict)
    async def run(
        self,
        query: str,
        query_type: str,
        memory_context: dict,
        user_context: dict
    ):
        """Route to appropriate backend and execute."""

        if query_type == "knowledge_question":
            # Use Certus-Ask (RAG)
            response = await self.certus_ask.query(query)
            return {
                "response": response["answer"],
                "backend_used": "certus-ask",
                "metadata": {"sources": response["sources"]}
            }

        elif query_type == "code_analysis":
            # Use Security SLM for fast analysis
            response = await self.slm.analyze_code(
                code=memory_context.get("code", ""),
                query=query
            )

            # If SLM confidence is low, escalate to GPT-4
            if response["confidence"] < 0.7:
                gpt4_response = await self._escalate_to_gpt4(query, response, memory_context)
                return {
                    "response": gpt4_response,
                    "backend_used": "security-slm+gpt4",
                    "metadata": {"slm_confidence": response["confidence"]}
                }

            return {
                "response": response["analysis"],
                "backend_used": "security-slm",
                "metadata": {"confidence": response["confidence"]}
            }

        elif query_type == "workflow_execution":
            # Use Goose agent for complex workflows
            response = await self.goose.execute_workflow(
                prompt=query,
                context={
                    "user_preferences": user_context.get("preferences", {}),
                    "conversation_history": memory_context.get("recent_messages", [])
                }
            )

            return {
                "response": response["result"],
                "backend_used": "goose-agent",
                "metadata": {
                    "steps_executed": response["steps"],
                    "tools_used": response["tools"]
                }
            }

        elif query_type == "data_query":
            # Query Certus-Insight
            response = await self.insight.query(query, user_context)
            return {
                "response": response["answer"],
                "backend_used": "certus-insight",
                "metadata": {"chart_data": response.get("visualization")}
            }

        else:
            # General conversation - use GPT-4
            response = await self._general_conversation(query, memory_context)
            return {
                "response": response,
                "backend_used": "gpt4",
                "metadata": {}
            }

    async def _escalate_to_gpt4(self, query: str, slm_response: dict, context: dict):
        """Escalate to GPT-4 when SLM confidence is low."""
        # Use GPT-4 for more detailed analysis
        pass

    async def _general_conversation(self, query: str, context: dict):
        """Handle general conversation with GPT-4."""
        pass

@component
class MemoryUpdater:
    """
    Update conversation memory after each interaction.

    Stores:
    - Message in PostgreSQL (structured data)
    - Embedding in OpenSearch (semantic search)
    - Updates user context/preferences if learned something new
    """

    def __init__(self, document_store: OpenSearchDocumentStore, db_client):
        self.document_store = document_store
        self.db = db_client
        self.embedder = SentenceTransformersTextEmbedder(
            model="sentence-transformers/all-MiniLM-L6-v2"
        )

    @component.output_types(success=bool)
    async def run(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_response: str,
        metadata: dict
    ):
        """Store conversation in memory."""

        # 1. Store in PostgreSQL (source of truth)
        await self.db.execute("""
            INSERT INTO messages (session_id, user_id, role, content, timestamp, metadata)
            VALUES
                ($1, $2, 'user', $3, NOW(), $4),
                ($1, $2, 'assistant', $5, NOW(), $6)
        """, session_id, user_id, user_message, {}, assistant_response, metadata)

        # 2. Generate embeddings
        user_embedding = self.embedder.run(user_message)["embedding"]
        assistant_embedding = self.embedder.run(assistant_response)["embedding"]

        # 3. Store in OpenSearch (for semantic search)
        await self.document_store.write_documents([
            {
                "content": user_message,
                "embedding": user_embedding,
                "meta": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "role": "user",
                    "timestamp": datetime.now().isoformat()
                }
            },
            {
                "content": assistant_response,
                "embedding": assistant_embedding,
                "meta": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "role": "assistant",
                    "timestamp": datetime.now().isoformat(),
                    **metadata
                }
            }
        ])

        # 4. Update user context if we learned something
        await self._update_user_context(user_id, user_message, assistant_response)

        return {"success": True}

    async def _update_user_context(self, user_id: str, user_msg: str, assistant_msg: str):
        """Learn and update user preferences."""
        # Example: If user mentions priority, store it
        if "priority" in user_msg.lower() or "focus on" in user_msg.lower():
            # Extract and store preference
            pass

# Build the main pipeline
def build_main_chat_pipeline(
    document_store: OpenSearchDocumentStore,
    db_client,
    slm_client,
    goose_client,
    certus_ask_client,
    insight_client
):
    """Build the main conversational pipeline."""

    pipeline = Pipeline()

    # Add components
    pipeline.add_component(
        "memory_retriever",
        ConversationMemoryRetriever(document_store, db_client)
    )
    pipeline.add_component(
        "query_classifier",
        QueryClassifier()
    )
    pipeline.add_component(
        "router",
        IntelligentRouter(slm_client, goose_client, certus_ask_client, insight_client)
    )
    pipeline.add_component(
        "memory_updater",
        MemoryUpdater(document_store, db_client)
    )

    # Connect components
    pipeline.connect("memory_retriever.recent_messages", "router.memory_context")
    pipeline.connect("memory_retriever.user_context", "router.user_context")
    pipeline.connect("query_classifier.query_type", "router.query_type")
    pipeline.connect("router.response", "memory_updater.assistant_response")

    return pipeline
```

#### 2. Memory Architecture

**Three-Tier Memory System:**

```python
# certus_chat/memory/architecture.py
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class Message:
    """Single message in a conversation."""
    id: str
    session_id: str
    user_id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    metadata: Dict

@dataclass
class ConversationSession:
    """A conversation session."""
    id: str
    user_id: str
    title: str  # Auto-generated or user-provided
    created_at: datetime
    updated_at: datetime
    message_count: int
    status: str  # 'active', 'archived'

@dataclass
class UserContext:
    """User-specific context and preferences."""
    user_id: str
    preferences: Dict  # e.g., {"detail_level": "high", "format": "markdown"}
    priorities: List[str]  # e.g., ["authentication", "sql-injection"]
    repositories: List[str]  # Frequently accessed repos
    team_id: str
    learning_history: Dict  # What the system has learned about this user

class HybridMemoryStore:
    """
    Hybrid memory using PostgreSQL + OpenSearch.

    PostgreSQL:
    - Source of truth for all conversations
    - Structured queries (get session, list messages)
    - User preferences and metadata

    OpenSearch (existing infrastructure):
    - Vector embeddings for semantic search
    - Full-text search capabilities
    - Hybrid search (vector + keyword)
    """

    def __init__(
        self,
        opensearch_store: OpenSearchDocumentStore,
        postgres_pool
    ):
        self.opensearch = opensearch_store
        self.db = postgres_pool

    async def save_message(self, message: Message):
        """Save message to both stores."""

        # 1. Save to PostgreSQL (structured)
        await self.db.execute("""
            INSERT INTO messages (id, session_id, user_id, role, content, timestamp, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, message.id, message.session_id, message.user_id, message.role,
             message.content, message.timestamp, message.metadata)

        # 2. Generate embedding
        embedding = await self._generate_embedding(message.content)

        # 3. Save to OpenSearch (vector + text)
        await self.opensearch.write_documents([{
            "content": message.content,
            "embedding": embedding,
            "meta": {
                "message_id": message.id,
                "session_id": message.session_id,
                "user_id": message.user_id,
                "role": message.role,
                "timestamp": message.timestamp.isoformat(),
                **message.metadata
            }
        }])

    async def get_recent_messages(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Message]:
        """Get recent messages from current session."""

        rows = await self.db.fetch("""
            SELECT id, session_id, user_id, role, content, timestamp, metadata
            FROM messages
            WHERE session_id = $1
            ORDER BY timestamp DESC
            LIMIT $2
        """, session_id, limit)

        return [Message(**dict(row)) for row in reversed(rows)]

    async def semantic_search(
        self,
        query: str,
        user_id: str,
        exclude_session: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """Search past conversations semantically."""

        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Search in OpenSearch
        filters = {"user_id": user_id}
        if exclude_session:
            filters["session_id"] = {"$ne": exclude_session}

        results = await self.opensearch.query_by_embedding(
            query_embedding=query_embedding,
            filters=filters,
            top_k=top_k
        )

        return results

    async def hybrid_search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Hybrid search: vector similarity + keyword matching.

        OpenSearch supports this natively.
        """

        query_embedding = await self._generate_embedding(query)

        # OpenSearch hybrid search
        results = await self.opensearch.query(
            query_embedding=query_embedding,
            query_text=query,  # Keyword search
            filters={"user_id": user_id},
            top_k=top_k,
            hybrid=True  # Combine vector + keyword scores
        )

        return results

    async def get_user_context(self, user_id: str) -> UserContext:
        """Load user context and preferences."""

        row = await self.db.fetchrow("""
            SELECT user_id, preferences, priorities, repositories, team_id, learning_history
            FROM users
            WHERE user_id = $1
        """, user_id)

        if row:
            return UserContext(**dict(row))
        else:
            # Create default context
            return UserContext(
                user_id=user_id,
                preferences={},
                priorities=[],
                repositories=[],
                team_id=None,
                learning_history={}
            )

    async def update_user_context(self, user_id: str, updates: Dict):
        """Update user preferences and context."""

        await self.db.execute("""
            UPDATE users
            SET
                preferences = COALESCE(preferences, '{}'::jsonb) || $2::jsonb,
                priorities = COALESCE(priorities, ARRAY[]::text[]) || $3::text[],
                learning_history = COALESCE(learning_history, '{}'::jsonb) || $4::jsonb,
                updated_at = NOW()
            WHERE user_id = $1
        """, user_id, updates.get("preferences", {}),
             updates.get("priorities", []), updates.get("learning_history", {}))

    async def create_session(self, user_id: str, title: Optional[str] = None) -> str:
        """Create a new conversation session."""

        session_id = str(uuid.uuid4())

        await self.db.execute("""
            INSERT INTO sessions (id, user_id, title, created_at, updated_at, status)
            VALUES ($1, $2, $3, NOW(), NOW(), 'active')
        """, session_id, user_id, title or "New Conversation")

        return session_id

    async def list_sessions(self, user_id: str, limit: int = 20) -> List[ConversationSession]:
        """List user's conversation sessions."""

        rows = await self.db.fetch("""
            SELECT id, user_id, title, created_at, updated_at,
                   (SELECT COUNT(*) FROM messages WHERE session_id = sessions.id) as message_count,
                   status
            FROM sessions
            WHERE user_id = $1
            ORDER BY updated_at DESC
            LIMIT $2
        """, user_id, limit)

        return [ConversationSession(**dict(row)) for row in rows]

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        embedder = SentenceTransformersTextEmbedder(
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
        result = embedder.run(text)
        return result["embedding"]
```

**Database Schema:**

```sql
-- PostgreSQL schema for conversation data

-- Users and their context
CREATE TABLE users (
    user_id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    team_id VARCHAR(255),
    preferences JSONB DEFAULT '{}'::jsonb,
    priorities TEXT[] DEFAULT ARRAY[]::text[],
    repositories TEXT[] DEFAULT ARRAY[]::text[],
    learning_history JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Conversation sessions
CREATE TABLE sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(user_id),
    title VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_sessions_user_updated ON sessions(user_id, updated_at DESC);

-- Messages
CREATE TABLE messages (
    id VARCHAR(255) PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255) REFERENCES users(user_id),
    role VARCHAR(50) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_messages_session_timestamp ON messages(session_id, timestamp);
CREATE INDEX idx_messages_user ON messages(user_id);

-- User preferences (for faster lookups)
CREATE TABLE user_preferences (
    user_id VARCHAR(255) REFERENCES users(user_id),
    key VARCHAR(255),
    value JSONB,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, key)
);

-- Team/organizational memory
CREATE TABLE team_context (
    team_id VARCHAR(255) PRIMARY KEY,
    shared_knowledge JSONB DEFAULT '{}'::jsonb,
    common_patterns JSONB DEFAULT '{}'::jsonb,
    policies JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**OpenSearch Index Mapping:**

```json
{
  "mappings": {
    "properties": {
      "content": {
        "type": "text",
        "analyzer": "standard"
      },
      "embedding": {
        "type": "knn_vector",
        "dimension": 384,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib"
        }
      },
      "meta": {
        "properties": {
          "message_id": {"type": "keyword"},
          "session_id": {"type": "keyword"},
          "user_id": {"type": "keyword"},
          "role": {"type": "keyword"},
          "timestamp": {"type": "date"},
          "backend_used": {"type": "keyword"}
        }
      }
    }
  }
}
```

#### 3. FastAPI Backend

```python
# certus_chat/api/main.py
from fastapi import FastAPI, WebSocket, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import asyncio

app = FastAPI(title="Certus Chat API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency injection
async def get_chat_service():
    """Get ChatService instance."""
    return chat_service  # Initialized at startup

# WebSocket for real-time chat
@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    user_id: str  # From auth token
):
    """WebSocket endpoint for real-time chat."""

    await websocket.accept()

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = data.get("message")

            # Process message through pipeline
            async for chunk in chat_service.stream_response(
                user_id=user_id,
                session_id=session_id,
                message=message
            ):
                # Stream response back to client
                await websocket.send_json({
                    "type": "chunk",
                    "content": chunk
                })

            # Send completion signal
            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")

# REST API endpoints

@app.post("/api/chat/message")
async def send_message(
    request: ChatMessageRequest,
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Send a message and get response (non-streaming)."""

    response = await chat_service.chat(
        user_id=user_id,
        session_id=request.session_id,
        message=request.message
    )

    return {
        "response": response["content"],
        "backend_used": response["backend"],
        "metadata": response["metadata"]
    }

@app.get("/api/chat/sessions")
async def list_sessions(
    user_id: str = Depends(get_current_user),
    limit: int = 20,
    chat_service: ChatService = Depends(get_chat_service)
):
    """List user's conversation sessions."""

    sessions = await chat_service.list_sessions(user_id, limit)
    return {"sessions": sessions}

@app.get("/api/chat/history/{session_id}")
async def get_conversation_history(
    session_id: str,
    user_id: str = Depends(get_current_user),
    limit: int = 50,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get conversation history for a session."""

    messages = await chat_service.get_history(session_id, user_id, limit)
    return {"messages": messages}

@app.post("/api/chat/sessions")
async def create_session(
    request: CreateSessionRequest,
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Create a new conversation session."""

    session_id = await chat_service.create_session(
        user_id=user_id,
        title=request.title
    )

    return {"session_id": session_id}

@app.post("/api/chat/search")
async def search_conversations(
    request: SearchRequest,
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Semantic search over conversation history."""

    results = await chat_service.search(
        user_id=user_id,
        query=request.query,
        top_k=request.top_k or 10
    )

    return {"results": results}

@app.get("/api/chat/suggestions")
async def get_suggestions(
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get proactive suggestions for the user."""

    suggestions = await chat_service.get_suggestions(user_id)
    return {"suggestions": suggestions}

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy"}
```

**ChatService Implementation:**

```python
# certus_chat/service/chat_service.py
class ChatService:
    """
    Main service orchestrating chat functionality.
    """

    def __init__(
        self,
        pipeline: Pipeline,
        memory_store: HybridMemoryStore,
        slm_client,
        goose_client
    ):
        self.pipeline = pipeline
        self.memory = memory_store
        self.slm = slm_client
        self.goose = goose_client

    async def chat(
        self,
        user_id: str,
        session_id: str,
        message: str
    ) -> Dict:
        """Process a chat message and return response."""

        # Run through Haystack pipeline
        result = await self.pipeline.run({
            "memory_retriever": {
                "query": message,
                "user_id": user_id,
                "session_id": session_id
            },
            "query_classifier": {
                "query": message
            }
        })

        return {
            "content": result["router"]["response"],
            "backend": result["router"]["backend_used"],
            "metadata": result["router"]["metadata"]
        }

    async def stream_response(
        self,
        user_id: str,
        session_id: str,
        message: str
    ):
        """Stream response in chunks (for WebSocket)."""

        # For streaming, we need to handle backends that support it
        # e.g., Goose agent streaming, GPT-4 streaming

        # Simplified example:
        response = await self.chat(user_id, session_id, message)

        # Simulate streaming by yielding chunks
        content = response["content"]
        chunk_size = 50

        for i in range(0, len(content), chunk_size):
            chunk = content[i:i+chunk_size]
            yield chunk
            await asyncio.sleep(0.05)  # Simulate latency

    async def list_sessions(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """List user's conversation sessions."""

        sessions = await self.memory.list_sessions(user_id, limit)
        return [
            {
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": s.message_count
            }
            for s in sessions
        ]

    async def get_history(
        self,
        session_id: str,
        user_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get conversation history."""

        messages = await self.memory.get_recent_messages(session_id, limit)
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "metadata": m.metadata
            }
            for m in messages
        ]

    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 10
    ) -> List[Dict]:
        """Semantic search over conversations."""

        results = await self.memory.hybrid_search(query, user_id, top_k)
        return results

    async def create_session(
        self,
        user_id: str,
        title: Optional[str] = None
    ) -> str:
        """Create new conversation session."""

        session_id = await self.memory.create_session(user_id, title)
        return session_id

    async def get_suggestions(self, user_id: str) -> List[Dict]:
        """Generate proactive suggestions."""

        # Example: Check for stale scans, pending issues, etc.
        suggestions = []

        # Load user context
        user_context = await self.memory.get_user_context(user_id)

        # Check repositories for stale scans
        for repo in user_context.repositories:
            last_scan = await self._get_last_scan(repo)
            if last_scan and (datetime.now() - last_scan["timestamp"]).days > 7:
                suggestions.append({
                    "type": "action",
                    "priority": "medium",
                    "message": f"Repository {repo} hasn't been scanned in {(datetime.now() - last_scan['timestamp']).days} days",
                    "suggested_action": f"Scan {repo}",
                    "action_command": f"scan {repo}"
                })

        return suggestions

    async def _get_last_scan(self, repo: str):
        """Get last scan timestamp for repository."""
        # Query Certus-Assurance or Insight
        pass
```

### Integration with AAIF and SLM

**Example: Chat invokes Goose agent:**

```python
# certus_chat/integrations/goose_integration.py
from goose_sdk import GooseClient

class GooseAgentIntegration:
    """Integration with Goose agents (AAIF)."""

    def __init__(self):
        self.client = GooseClient(profile="certus-security")

    async def execute_workflow(
        self,
        prompt: str,
        context: Dict
    ) -> Dict:
        """Execute a workflow via Goose agent."""

        # Enhance prompt with conversation context
        enhanced_prompt = self._build_contextual_prompt(prompt, context)

        # Invoke Goose
        result = await self.client.run(enhanced_prompt)

        return {
            "result": result["output"],
            "steps": result["steps_executed"],
            "tools": result["tools_used"]
        }

    def _build_contextual_prompt(self, prompt: str, context: Dict) -> str:
        """Build prompt with conversation context."""

        context_str = ""

        # Add user preferences
        if context.get("user_preferences"):
            prefs = context["user_preferences"]
            if prefs.get("priorities"):
                context_str += f"\nUser priorities: {', '.join(prefs['priorities'])}"

        # Add recent conversation
        if context.get("conversation_history"):
            context_str += "\n\nRecent conversation:\n"
            for msg in context["conversation_history"][-3:]:
                context_str += f"{msg['role']}: {msg['content']}\n"

        return f"{context_str}\n\nCurrent request: {prompt}"
```

**Example: Two-tier routing (SLM → GPT-4):**

```python
# User asks about code security
User: "Is this code vulnerable?"
  ↓
Chat Pipeline:
  ↓
QueryClassifier → "code_analysis"
  ↓
Router:
  1. Try Security SLM first (fast, cheap)
     → SLM analyzes: "Possible SQL injection, confidence: 0.65"
  2. Confidence < 0.7, escalate to GPT-4
     → GPT-4: "Yes, SQL injection. Here's why... Here's the fix..."
  ↓
Response: GPT-4 detailed analysis
Memory: Store conversation + learned that this user asks about Python SQL code
```

### Proactive Features

```python
# certus_chat/proactive/assistant.py
class ProactiveAssistant:
    """Proactive features: notifications, suggestions, automation."""

    async def check_and_notify(self, user_id: str):
        """Check for items requiring user attention."""

        notifications = []

        # 1. Check for stale scans
        stale_scans = await self._check_stale_scans(user_id)
        notifications.extend(stale_scans)

        # 2. Check for new CVEs affecting user's repos
        cve_alerts = await self._check_new_cves(user_id)
        notifications.extend(cve_alerts)

        # 3. Check for pending high-priority issues
        pending_issues = await self._check_pending_issues(user_id)
        notifications.extend(pending_issues)

        return notifications

    async def auto_title_session(self, session_id: str):
        """Auto-generate title for conversation session."""

        # Get first few messages
        messages = await memory.get_recent_messages(session_id, limit=5)

        # Use SLM to generate title
        context = "\n".join([f"{m.role}: {m.content}" for m in messages])

        title = await slm.generate_title(context)

        # Update session
        await db.execute("""
            UPDATE sessions SET title = $1 WHERE id = $2
        """, title, session_id)
```

## Use Cases & Examples

### Example 1: First-Time User

```
User opens Certus Chat for the first time

System: "Hi! I'm your Certus security assistant. I can help you:
         • Scan repositories for vulnerabilities
         • Answer security questions
         • Track your security posture
         • And more!

         What would you like to do?"

User: "Scan my api-server repository"

System: "Great! I'll scan api-server for you.
         Quick question: Should I use a light scan (faster, good for CI)
         or heavy scan (thorough, all tools)?"

User: "Heavy scan"

System: [Invokes Goose agent → Certus-Assurance MCP]
        "Starting heavy scan on api-server...

         ✓ Trivy: Complete
         ✓ Semgrep: Complete
         ✓ Bandit: Complete

         Scan complete! Found 23 issues:
         • 2 critical (SQL injection, XSS)
         • 5 high
         • 16 medium

         The 2 critical issues are:
         1. SQL injection in src/auth.py:45
         2. XSS in templates/profile.html:12

         Would you like me to create a fix plan?"

User: "Yes, and prioritize authentication issues going forward"

System: [Stores preference: user prioritizes auth]
        "Got it! I'll always highlight auth issues for you.

         Here's the fix plan for the SQL injection in auth.py:
         [Shows detailed plan with code examples]

         Should I create a PR with the fix?"

[Memory stored: User cares about auth, uses api-server, prefers heavy scans]
```

### Example 2: Returning User (Memory in Action)

```
User returns 3 days later

System: [Remembers context]
        "Welcome back!

         FYI: I noticed you haven't scanned api-server in 3 days.
         Would you like me to run a scan?"

User: "Yes"

System: [Remembers: user prefers heavy scans, prioritizes auth]
        "Running heavy scan on api-server (focusing on auth issues)...

         Good news! No new critical issues.
         However, I found a new medium-severity auth issue:
         • Weak password policy in src/auth/password.py

         Since you prioritize authentication, I flagged this for you.
         Want me to fix it?"

User: "What's wrong with it?"

System: [Uses Certus-Ask for knowledge]
        "The current password policy allows passwords as short as 6 characters
         with no complexity requirements. NIST recommends minimum 8 characters.

         Here's the current code:
         [Shows code]

         I recommend changing MIN_LENGTH to 8 and adding complexity checks."

User: "Fix it"

System: [Goose agent creates fix]
        "Done! I've created a PR with the fix: #456

         The fix:
         • Increases minimum length to 8
         • Requires at least one letter and one number
         • Updated tests

         All tests passing ✓"
```

### Example 3: Team Collaboration

```
Developer A:
User: "I'm investigating the SQL injection in auth.py"

System: "Got it. I'll track your work on this.

         Here's what I found about this issue:
         • Reported 3 days ago by security scan
         • CVSS: 9.8 (Critical)
         • No exploit in the wild yet

         Should I notify your team that you're working on this?"

User: "Yes, notify the security team"

System: [Sends notification to security team channel]
        "Notified #security-team. I'll keep them updated on your progress."

---

[2 hours later, Developer B from security team opens chat]

Developer B:
User: "What's the status on the auth.py SQL injection?"

System: [Shares context from Developer A's session]
        "Developer A started fixing this 2 hours ago. Here's the conversation:
         [Shows relevant excerpts]

         They're currently testing the fix. Would you like me to connect
         you with their session?"

Developer B: "Yes"

System: [Creates shared session]
        "I've created a shared workspace. Both you and Developer A can
         see this conversation now."

Developer A & B can now collaborate in real-time with shared context
```

### Example 4: Proactive Notification

```
System detects new CVE affecting user's repositories

System: [Sends notification]
        "🚨 Security Alert

         CVE-2025-12345 was published today affecting Django 4.1.x

         I checked your repositories and found:
         • api-server: Django 4.1.7 ❌ (vulnerable)
         • payment-service: Django 4.2.1 ✓ (not vulnerable)

         Recommendation: Upgrade api-server to Django 4.1.13

         Should I create an upgrade PR?"

User: "Yes, but run tests first"

System: [Goose agent workflow]
        "Creating upgrade PR...

         ✓ Updated requirements.txt (Django 4.1.7 → 4.1.13)
         ✓ Updated lock file
         ✓ Running tests... (127 tests)
         ✓ All tests passed

         PR #457 created: 'Security: Upgrade Django to 4.1.13 (CVE-2025-12345)'

         Ready for review!"
```

### Example 5: Data Exploration

```
User: "Show me our security trends for the last 3 months"

System: [Routes to Certus-Insight]
        "Here's your security overview for Oct-Dec 2025:

         📊 Overall Trend: ✅ Improving

         Critical Issues:
         Oct: 12 → Nov: 8 → Dec: 3 (75% reduction)

         Mean Time to Fix:
         Oct: 6 days → Nov: 4 days → Dec: 2 days (67% faster)

         Most Common Issues:
         1. SQL Injection (15 occurrences)
         2. XSS (12 occurrences)
         3. Outdated Dependencies (45 occurrences)

         [Shows interactive chart]

         Your focus on authentication (started in October) has paid off:
         Zero auth issues in December! 🎉"

User: "What about the SQL injection issues?"

System: [Remembers context from chart]
        "Good question. Of the 15 SQL injection issues:

         • 12 were in api-server (all fixed)
         • 2 were in payment-service (1 remaining)
         • 1 was in admin-panel (fixed)

         The remaining issue is:
         payment-service: src/reports.py:234 (Medium severity)

         Want me to fix it?"
```

## Phased Roadmap

### Phase 0: Foundation (Weeks 1-2)

**Goals:**
- Set up development environment
- Design Haystack pipeline architecture
- Database schema design (PostgreSQL + OpenSearch)
- API design and contracts

**Deliverables:**
- Architecture documentation
- Database schema (SQL)
- OpenSearch index mappings
- API specification (OpenAPI)
- Development environment setup guide

**Success Criteria:**
- Architecture reviewed and approved
- Database schema implemented in dev
- OpenSearch index created
- API contracts defined

### Phase 1: Core Chat (Weeks 3-6)

**Goals:**
- Build basic Haystack pipeline
- Implement FastAPI backend (WebSocket + REST)
- Build React frontend (web chat UI)
- Short-term memory (in-session context)
- Integration with Certus-Ask (RAG)

**Deliverables:**
- Haystack pipeline (basic version)
- FastAPI backend (WebSocket + REST)
- React chat UI (web)
- Short-term memory implementation
- Certus-Ask integration
- Docker compose for local dev

**Success Criteria:**
- Users can chat via web interface
- Conversation maintains context within session
- Questions routed to Certus-Ask successfully
- WebSocket streaming works
- <2 second response time (p95)

### Phase 2: Memory & Routing (Weeks 7-10)

**Goals:**
- Implement long-term memory (OpenSearch + PostgreSQL)
- Semantic search over conversation history
- Intelligent routing (SLM, AAIF, Certus services)
- User preferences and context
- Conversation history UI

**Deliverables:**
- Hybrid memory store (OpenSearch + PostgreSQL)
- Semantic search functionality
- Intelligent routing component
- User preferences system
- Conversation history browser
- Search functionality in UI

**Success Criteria:**
- Users can search past conversations semantically
- System remembers user preferences across sessions
- Routing accuracy >90%
- Can retrieve relevant context from past conversations

### Phase 3: AAIF & SLM Integration (Weeks 11-14)

**Goals:**
- Integrate with Goose agents (AAIF)
- Integrate with Security SLM
- Two-tier routing (SLM → GPT-4 escalation)
- Workflow execution via agents
- Progress streaming for long-running tasks

**Deliverables:**
- Goose agent integration
- Security SLM integration
- Two-tier routing logic
- Workflow progress streaming
- Agent execution visualization in UI

**Success Criteria:**
- Chat can invoke Goose agents for workflows
- Security SLM handles fast classification
- Escalation to GPT-4 works when SLM confidence low
- Users see real-time progress for agent executions
- 80%+ cost reduction via SLM first-tier

### Phase 4: Proactive Features (Weeks 15-18)

**Goals:**
- Proactive notifications and suggestions
- Auto-title generation for sessions
- Team collaboration features
- Shared conversations
- @mentions and handoffs

**Deliverables:**
- Proactive notification system
- Auto-title generation (SLM-powered)
- Team workspace features
- Shared conversation UI
- @mention functionality
- Background job system (check for alerts)

**Success Criteria:**
- Users receive relevant proactive notifications
- Session titles auto-generated accurately
- Teams can collaborate on shared conversations
- @mentions notify team members
- Notification relevance >80%

### Phase 5: Scale & Polish (Weeks 19-22)

**Goals:**
- Performance optimization
- Mobile web optimization
- Messaging platform integrations (Slack, Teams)
- Analytics and insights
- Production deployment

**Deliverables:**
- Performance optimization (caching, batching)
- Mobile-optimized UI
- Slack bot integration
- Microsoft Teams bot integration
- Analytics dashboard
- Production deployment (Kubernetes)
- Monitoring and alerting

**Success Criteria:**
- p95 response time <1 second
- Mobile UI works well on all devices
- Slack/Teams bots functional
- 99.9% uptime
- Comprehensive monitoring in place

## Success Metrics

### Adoption Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Weekly Active Users** | 80% of developers | Unique users per week |
| **Daily Messages** | 1000+ messages/day by Week 16 | Message count |
| **Session Length** | >5 minutes average | Time spent per session |
| **Return Rate** | 70%+ return within 7 days | % users returning |

### Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Response Time (p95)** | <2 seconds | API latency |
| **Routing Accuracy** | >90% | % queries routed correctly |
| **Memory Retrieval** | <500ms | Time to load context |
| **Search Accuracy** | >85% | % relevant results in top 5 |

### Business Impact Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Productivity Gain** | 50%+ faster tasks | Time tracking before/after |
| **Query Success Rate** | >90% | % queries answered successfully |
| **User Satisfaction** | 4.5/5 | Post-interaction surveys |
| **Collaboration** | 30%+ shared sessions | % sessions with multiple users |

### Cost Efficiency Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Cost per Query** | <$0.02 | Total AI costs / query count |
| **SLM Usage Rate** | 60%+ | % queries handled by SLM |
| **LLM Call Reduction** | 50%+ | Reduction vs. all-GPT-4 |

## Technology Stack

### Frontend
```
React 18 + TypeScript
├─ UI Framework: TailwindCSS
├─ State Management: Zustand
├─ Real-time: WebSocket API
├─ Code Rendering: Monaco Editor (for code snippets)
├─ Charts: Recharts (for visualizations)
└─ Build: Vite
```

### Backend
```
Python 3.11+
├─ Web Framework: FastAPI
├─ Pipelines: Haystack AI ✅ (existing infrastructure)
├─ WebSocket: FastAPI WebSocket support
├─ Task Queue: Celery + Redis (background jobs)
└─ ASGI Server: Uvicorn
```

### Data Layer
```
Memory/Storage:
├─ OpenSearch ✅ (existing infrastructure)
│   ├─ Vector embeddings (semantic search)
│   ├─ Full-text search
│   └─ Hybrid search (vector + keyword)
├─ PostgreSQL
│   ├─ Conversation metadata
│   ├─ User preferences
│   └─ Session data
└─ Redis
    ├─ Session state
    ├─ Rate limiting
    └─ Cache
```

### Integration
```
AI/Agents:
├─ Security SLM Client (HTTP)
├─ Goose Agent SDK (AAIF)
├─ MCP Client (call Certus MCP servers)
├─ OpenAI SDK (GPT-4)
└─ Anthropic SDK (Claude, optional)

Certus Services:
├─ Certus-Assurance API
├─ Certus-Trust API
├─ Certus-Insight API
├─ Certus-Ask API
└─ Certus-Transform API
```

### Infrastructure
```
Deployment:
├─ Kubernetes (TAP environment)
├─ Docker containers
├─ NGINX (reverse proxy, load balancer)
└─ Cert-manager (TLS)

Monitoring:
├─ Prometheus (metrics)
├─ Grafana (dashboards)
├─ Sentry (error tracking)
└─ OpenTelemetry (tracing)
```

## Dependencies

### External Dependencies

**Python Libraries:**
- `fastapi` - Web framework
- `haystack-ai` - Pipeline orchestration ✅
- `opensearch-py` - OpenSearch client ✅
- `asyncpg` - PostgreSQL async client
- `redis` - Redis client
- `websockets` - WebSocket support
- `sentence-transformers` - Embeddings
- `pydantic` - Data validation

**Frontend Libraries:**
- `react` - UI framework
- `typescript` - Type safety
- `tailwindcss` - Styling
- `zustand` - State management
- `monaco-editor` - Code rendering

### Internal Dependencies

- **Certus Services** - All services must expose REST APIs
- **Security SLM** - From SLM proposal (for fast classification)
- **AAIF Infrastructure** - Goose agents, MCP servers
- **Certus TAP** - Platform for deployment
- **Existing OpenSearch** - For vector storage ✅
- **Existing Haystack** - For pipelines ✅

## Risks & Mitigations

### Risks

1. **Memory Storage Costs**
   - Risk: Storing all conversations could be expensive
   - Impact: High storage costs at scale
   - Mitigation: Retention policies (delete old conversations)
   - Mitigation: Compress old messages
   - Mitigation: Archive inactive sessions to cheaper storage

2. **Context Window Limits**
   - Risk: Long conversations exceed LLM context limits
   - Impact: Lost context, degraded experience
   - Mitigation: Summarization of old messages
   - Mitigation: Intelligent context selection (most relevant messages)
   - Mitigation: Use models with large context (Claude 200K)

3. **Routing Errors**
   - Risk: Query routed to wrong backend
   - Impact: Poor answers, user frustration
   - Mitigation: Monitor routing accuracy
   - Mitigation: Allow user to re-route ("Ask Goose agent instead")
   - Mitigation: Continuous improvement of classifier

4. **Privacy Concerns**
   - Risk: Sensitive data in conversation history
   - Impact: Compliance issues, user trust
   - Mitigation: Encryption at rest and in transit
   - Mitigation: User controls (delete conversation, export data)
   - Mitigation: Redaction of sensitive data (API keys, passwords)

5. **OpenSearch Performance**
   - Risk: Slow semantic search at scale
   - Impact: Poor user experience
   - Mitigation: Index optimization (HNSW parameters)
   - Mitigation: Caching of frequent queries
   - Mitigation: Hybrid search (vector + keyword) for better performance

6. **WebSocket Scaling**
   - Risk: Many concurrent connections
   - Impact: Server overload
   - Mitigation: Horizontal scaling (multiple pods)
   - Mitigation: Connection pooling
   - Mitigation: Rate limiting

### Non-Risks

- **Haystack/OpenSearch replacement** - We're using existing infrastructure ✅
- **Competing with AAIF** - This complements, doesn't compete
- **Data privacy** - All data stays in Certus infrastructure
- **Vendor lock-in** - Open-source stack (Haystack, OpenSearch, FastAPI, React)

## Cost Analysis

### Infrastructure Costs

| Component | Cost | Notes |
|-----------|------|-------|
| **OpenSearch** | $0 | Existing infrastructure ✅ |
| **PostgreSQL** | ~$50/month | Small RDS instance |
| **Redis** | ~$30/month | ElastiCache small instance |
| **Compute (Kubernetes)** | ~$200/month | 4 pods (API, WebSocket, workers) |
| **Storage** | ~$20/month | Conversation storage |
| **Total Infrastructure** | **~$300/month** | |

### AI/LLM Costs

Assuming 10K messages/day with intelligent routing:

| Scenario | Cost | Notes |
|----------|------|-------|
| **All GPT-4** (baseline) | ~$1,000/month | 10K × $0.10 |
| **With SLM first-tier** | ~$200/month | 60% SLM ($0.001), 40% GPT-4 |
| **With routing optimization** | ~$150/month | Better routing, caching |
| **Savings vs. baseline** | **$850/month** | 85% reduction |

### Total Monthly Costs

- Infrastructure: $300
- AI/LLM: $150
- **Total: ~$450/month**

### ROI

**Productivity gains:**
- 1000 users × 30 min saved/week = 500 hours/week
- 500 hours × $100/hour (loaded cost) = $50K/week value
- Monthly value: **$200K**

**ROI: 444x** ($200K value / $450 cost)

## Next Steps

### Immediate Actions (Week 1)

1. ✅ Review and approve this proposal
2. ✅ Assign team (2 backend engineers, 1 frontend engineer)
3. ✅ Validate Haystack + OpenSearch setup (already exists ✅)
4. ✅ Create project repositories:
   - `certus/certus-chat-backend`
   - `certus/certus-chat-frontend`
5. ✅ Set up development environment

### Phase 0 Kickoff (Weeks 1-2)

1. Design Haystack pipeline architecture in detail
2. Design database schema (PostgreSQL)
3. Design OpenSearch index mappings
4. Define API contracts (OpenAPI spec)
5. Create detailed Phase 1 backlog
6. Set up CI/CD pipelines

### Communication Plan

1. **Internal:**
   - Present proposal to engineering + product teams
   - Weekly demos during development
   - Beta program with 10 early users (Week 6)
   - Monthly showcases after launch

2. **External (post-Phase 3):**
   - Blog post: "Introducing Certus Chat"
   - Webinar: "AI-Powered Security Conversations"
   - Documentation: User guide, API reference
   - Video tutorials

### Success Criteria for Approval

- [ ] Strategic alignment (complements AAIF + SLM proposals)
- [ ] Leverages existing infrastructure (Haystack ✅, OpenSearch ✅)
- [ ] Architecture is sound (Haystack pipelines, hybrid memory)
- [ ] ROI is compelling (444x based on productivity gains)
- [ ] Phased approach is realistic (22 weeks to full launch)
- [ ] Resource allocation approved (3 engineers, infrastructure)
- [ ] Stakeholders support the unified interface vision

---

## Appendix A: Haystack Pipeline Examples

### Example: RAG Pipeline for Knowledge Questions

```python
from haystack import Pipeline
from haystack.document_stores.opensearch import OpenSearchDocumentStore
from haystack.components.retrievers import OpenSearchEmbeddingRetriever
from haystack.components.generators import OpenAIGenerator
from haystack.components.builders import PromptBuilder

def build_rag_pipeline(document_store: OpenSearchDocumentStore):
    """Build RAG pipeline for knowledge questions."""

    pipeline = Pipeline()

    # Components
    pipeline.add_component(
        "retriever",
        OpenSearchEmbeddingRetriever(document_store=document_store)
    )

    pipeline.add_component(
        "prompt_builder",
        PromptBuilder(template="""
            Context from knowledge base:
            {% for doc in documents %}
                {{ doc.content }}
            {% endfor %}

            User question: {{ question }}

            Answer the question based on the context above. If the context
            doesn't contain relevant information, say so.
        """)
    )

    pipeline.add_component(
        "llm",
        OpenAIGenerator(model="gpt-4-turbo", api_key=os.getenv("OPENAI_API_KEY"))
    )

    # Connections
    pipeline.connect("retriever.documents", "prompt_builder.documents")
    pipeline.connect("prompt_builder.prompt", "llm.prompt")

    return pipeline
```

### Example: Hybrid Search Pipeline

```python
from haystack import Pipeline, component

@component
class HybridSearchComponent:
    """Combine vector and keyword search in OpenSearch."""

    def __init__(self, document_store: OpenSearchDocumentStore):
        self.document_store = document_store

    @component.output_types(documents=list)
    async def run(self, query: str, query_embedding: list, top_k: int = 10):
        """
        Hybrid search: vector similarity + keyword matching.

        OpenSearch supports this natively via hybrid query.
        """

        # Use OpenSearch hybrid search
        # This combines:
        # - Neural search (vector similarity via kNN)
        # - Lexical search (BM25 keyword matching)

        results = await self.document_store.query(
            query_embedding=query_embedding,
            query_text=query,
            filters=filters,
            top_k=top_k,
            search_type="hybrid"  # Enable hybrid search
        )

        return {"documents": results}
```

---

## Appendix B: Database Migrations

### Initial Migration (PostgreSQL)

```sql
-- migrations/001_initial_schema.sql

-- Enable pgcrypto for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table
CREATE TABLE users (
    user_id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    team_id VARCHAR(255),
    preferences JSONB DEFAULT '{}'::jsonb,
    priorities TEXT[] DEFAULT ARRAY[]::text[],
    repositories TEXT[] DEFAULT ARRAY[]::text[],
    learning_history JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Sessions table
CREATE TABLE sessions (
    id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_sessions_user_updated ON sessions(user_id, updated_at DESC);

-- Messages table
CREATE TABLE messages (
    id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id VARCHAR(255) REFERENCES sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255) REFERENCES users(user_id),
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_messages_session_timestamp ON messages(session_id, timestamp);
CREATE INDEX idx_messages_user ON messages(user_id);

-- Team context table
CREATE TABLE team_context (
    team_id VARCHAR(255) PRIMARY KEY,
    shared_knowledge JSONB DEFAULT '{}'::jsonb,
    common_patterns JSONB DEFAULT '{}'::jsonb,
    policies JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

**End of Proposal**
