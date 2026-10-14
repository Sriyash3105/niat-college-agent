from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agent.orchestrator import run_comparison_agent  # noqa: E402
from services.tts_service import STATIC_DIR, synthesize_speech  # noqa: E402

app = FastAPI(title="NIAT Compare My College Agent")

STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CompareRequest(BaseModel):
    college_name: str = Field(..., min_length=2)
    language: str = "English"
    parent_name: str | None = None


class ComparisonPoint(BaseModel):
    aspect: str
    competitor: str
    niat: str


class CompareResponse(BaseModel):
    competitor_summary: str
    comparison_points: list[ComparisonPoint]
    parent_script_native: str
    audio_url: str | None
    tools_called: list[str] = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/compare", response_model=CompareResponse)
async def compare(req: CompareRequest):
    load_dotenv(override=True)  # pick up edited API keys without a server restart
    try:
        result = await run_in_threadpool(
            run_comparison_agent, req.college_name, req.language, req.parent_name
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent failed: {exc}") from exc

    # A TTS failure shouldn't throw away the comparison; return it without audio.
    audio_url = None
    try:
        filename = await run_in_threadpool(
            synthesize_speech, result["parent_script_native"], req.language
        )
        audio_url = f"/static/{filename}"
    except Exception as exc:
        print(f"TTS failed: {exc}")

    return CompareResponse(**result, audio_url=audio_url)
