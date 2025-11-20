# LangGraph Setup

Optional LangGraph Studio for visualizing agent execution.

---

## LangGraph Studio (Free Local)

### Install

Download from https://studio.langchain.com

### Configuration

Project already configured in `langgraph.json`:

```json
{
  "graphs": {
    "conversational_ai": "./podcast-summarizer/backend/services/agents/conversational_ai_agent.py:graph",
    "general_ai": "./podcast-summarizer/backend/services/agents/general_ai_agent.py:graph",
    "research_opinion": "./podcast-summarizer/backend/services/agents/research_opinion_agent.py:graph"
  },
  "env": ".env"
}
```

### Start Studio

```bash
# From project root
langgraph dev
```

Studio opens at http://127.0.0.1:2024

### Features

- Visualize agent execution graph
- Step-through debugging
- View LLM calls and responses
- Inspect state at each node
- Manual input/output testing

---

## LangSmith Tracing (Optional)

### Setup

1. Sign up at https://smith.langchain.com
2. Get API key from settings
3. Add to `.env`:

```bash
LANGSMITH_API_KEY=lsv2_pt_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=morning-automation
```

### Features

- Trace all LLM calls
- Monitor costs and latency
- Debug agent execution
- View full conversation history

---

## Testing Agents

### Run Individual Agent

```bash
cd podcast-summarizer
python -m backend.services.agents.conversational_ai_agent
```

### Run All Agents (Orchestrator)

```bash
TEST_MODE=true python tests/test_agent_search.py
```

### View in LangSmith

If LANGSMITH_API_KEY is set, traces appear at:
https://smith.langchain.com/o/YOUR_ORG/projects

---

## Troubleshooting

### langgraph command not found
```bash
pip install langgraph-cli
```

### Studio won't start
- Check port 2024 not in use: `lsof -i :2024`
- Verify langgraph.json paths are correct
- Check .env file exists with API keys

### Agents not visible in Studio
- Verify graph exports in agent files
- Check imports are correct
- Restart Studio after code changes

### LangSmith traces not appearing
- Verify LANGSMITH_API_KEY is set
- Check LANGCHAIN_TRACING_V2=true
- Confirm internet connection
- Check API key is valid


