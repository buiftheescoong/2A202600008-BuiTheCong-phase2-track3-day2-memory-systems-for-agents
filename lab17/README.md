# Lab #17: Multi-Memory Agent with LangGraph


## Memory Stack

| Type | Backend | Purpose |
|------|---------|---------|
| Short-term | Sliding window buffer | Recent conversation context |
| Long-term | Redis (Docker) | User profile facts (name, preferences, allergies) |
| Episodic | JSON file | Past experiences, lessons learned, task outcomes |
| Semantic | ChromaDB (persistent) | Knowledge base retrieval via vector search |

## Setup

### 1. Prerequisites
- Python 3.10+
- Docker & Docker Compose
- Google API Key (Gemini)

### 2. Install

```bash
cd lab17
pip install -r requirements.txt
```

### 3. Configure

Edit `.env`:
```
GOOGLE_API_KEY=your-key-here
REDIS_URL=redis://localhost:6379
```

### 4. Start Redis

```bash
docker compose up -d
```

### 5. Run Agent

```bash
python main.py
```

### 6. Run Benchmark

```bash
python -m benchmark.runner
```

## Commands (in chat)

- `stats` - View memory stats
- `profile` - View user profile
- `graph` - Show LangGraph Mermaid diagram
- `quit` - Exit

## Bonus Features

- **Redis real** (+2): Docker Redis 7 with AOF persistence
- **ChromaDB real** (+2): Persistent vector store with cosine similarity
- **LLM extraction** (+2): Gemini-based fact extraction with JSON parse + retry
- **Token counting** (+2): tiktoken (cl100k_base) accurate counting
- **Graph flow** (+2): LangGraph StateGraph with Mermaid export
