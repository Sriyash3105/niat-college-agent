# NIAT "Compare My College" Agent

An agentic, multilingual tool for admission counselors. Enter a competitor engineering college and the parent's preferred language; the agent researches the college live on the web, compares it point-by-point against NIAT's verified facts, and generates a personalised voice note for the parent in Telugu, Hindi, Tamil or English.

## How it works

```
Streamlit UI ──POST /compare──▶ FastAPI
                                  │
                                  ├─▶ LLM agent (Gemini, OpenAI-compatible tool calling)
                                  │     ├─ tool: search_competitor_college  → Tavily web search
                                  │     └─ tool: get_niat_facts             → data/niat_grounding.json
                                  │
                                  ├─▶ JSON: competitor summary, comparison matrix, native-language script
                                  └─▶ edge-tts → MP3 in static/ (native Telugu/Hindi/Tamil voices)
```

| Layer | Tech | Cost |
|---|---|---|
| Frontend | Streamlit | – |
| Backend | FastAPI + Uvicorn | – |
| LLM / agent | Google Gemini via OpenAI SDK (any OpenAI-compatible provider works) | Free tier |
| Web research | Tavily Search API | Free: 1,000 credits/month |
| Voice | edge-tts (Microsoft neural voices) | Free, no key |

## Project structure

```
├── main.py                  # FastAPI app: POST /compare, GET /health, /static audio
├── app.py                   # Streamlit counselor portal
├── agent/
│   ├── orchestrator.py      # Tool-calling loop, rate-limit retries, JSON parsing
│   ├── prompts.py           # System prompt (empathetic counselor, strict JSON output)
│   └── tools.py             # Tavily search + NIAT facts tools and their schemas
├── services/
│   └── tts_service.py       # edge-tts voice synthesis
├── data/
│   └── niat_grounding.json  # The only NIAT claims the agent is allowed to make
└── static/                  # Generated MP3s (gitignored)
```

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone <this-repo-url>
cd niat-college-agent
uv sync
cp .env.example .env
```

Add free API keys to `.env`:

- `LLM_API_KEY`: Gemini key from https://aistudio.google.com/apikey
- `TAVILY_API_KEY`: from https://app.tavily.com

## Run

In two terminals:

```bash
uv run uvicorn main:app --reload --port 8000   # backend  → http://localhost:8000/docs
uv run streamlit run app.py                    # frontend → http://localhost:8501
```

Or call the API directly:

```bash
curl -X POST localhost:8000/compare -H 'Content-Type: application/json' \
  -d '{"college_name": "CMR College of Engineering and Technology, Hyderabad", "language": "Telugu", "parent_name": "Ramesh garu"}'
```

A request takes roughly 30–60 seconds.

The Streamlit app talks to the FastAPI backend only when `BACKEND_URL` is set. If it isn't, the app runs the agent and voice synthesis in-process, so `uv run streamlit run app.py` alone is enough.

## Deploy on Streamlit Community Cloud

1. On https://share.streamlit.io, create an app from this repo with `app.py` as the main file.
2. Under **Advanced settings → Secrets**, add:
   ```toml
   LLM_API_KEY = "your-gemini-key"
   TAVILY_API_KEY = "tvly-your-key"
   ```
3. Do **not** set `BACKEND_URL`; the app runs everything in-process.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `LLM_API_KEY` | – (required) | API key for the LLM provider |
| `TAVILY_API_KEY` | – (required) | Tavily search key |
| `LLM_BASE_URL` | Gemini's OpenAI-compatible endpoint | Switch to another OpenAI-compatible provider (e.g. Groq, OpenAI) |
| `LLM_MODEL` | `gemini-flash-lite-latest` | Model name |
| `BACKEND_URL` | unset | If set, the Streamlit app calls this FastAPI backend instead of running the agent in-process |

## Notes

- **Grounding:** the agent may only make NIAT claims present in `data/niat_grounding.json`. Verify those figures against official NIAT material before real use.
- **Free-tier limits:** Gemini's free tier allows only a few requests per minute. The orchestrator waits and retries on 429/503 responses, so back-to-back runs may be slower rather than fail.
- **Privacy:** Gemini free-tier requests may be used by Google to improve its models; avoid entering real parents' personal details.
- `requirements.txt` is exported from `uv.lock` for platforms such as Render/Railway: `uv export --no-hashes --no-dev -o requirements.txt`.
