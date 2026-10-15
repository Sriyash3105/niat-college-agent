import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# With BACKEND_URL set, the app calls the FastAPI backend. Without it (e.g. on
# Streamlit Community Cloud) the agent and TTS run directly in this process.
BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")
LANGUAGES = ["Telugu", "Hindi", "Tamil", "English"]


class ComparisonError(Exception):
    pass


def compare_via_backend(college_name: str, language: str, parent_name: str | None):
    try:
        resp = requests.post(
            f"{BACKEND_URL}/compare",
            json={
                "college_name": college_name,
                "language": language,
                "parent_name": parent_name,
            },
            timeout=180,
        )
    except requests.RequestException as exc:
        raise ComparisonError(f"Could not reach backend at {BACKEND_URL}: {exc}")
    if not resp.ok:
        raise ComparisonError(f"Backend error: {resp.text}")
    result = resp.json()

    # Fetch bytes server-side so this works even when the backend isn't publicly reachable.
    audio = None
    if result.get("audio_url"):
        try:
            audio_resp = requests.get(f"{BACKEND_URL}{result['audio_url']}", timeout=30)
            audio_resp.raise_for_status()
            audio = audio_resp.content
        except requests.RequestException:
            pass
    return result, audio


def compare_in_process(college_name: str, language: str, parent_name: str | None):
    from agent.orchestrator import run_comparison_agent
    from services.tts_service import STATIC_DIR, synthesize_speech

    missing = [k for k in ("LLM_API_KEY", "TAVILY_API_KEY") if not os.getenv(k)]
    if missing:
        raise ComparisonError(
            f"Missing secrets: {', '.join(missing)}. Add them in the app's Secrets settings."
        )

    try:
        result = run_comparison_agent(college_name, language, parent_name)
    except Exception as exc:
        raise ComparisonError(f"Agent failed: {exc}")

    # A TTS failure shouldn't throw away the comparison; show it without audio.
    audio = None
    try:
        path = STATIC_DIR / synthesize_speech(result["parent_script_native"], language)
        audio = path.read_bytes()
        path.unlink()
    except Exception as exc:
        print(f"TTS failed: {exc}")
    return result, audio


st.set_page_config(
    page_title="NIAT · Compare My College", page_icon="🎓", layout="wide"
)
st.title("🎓 Compare My College")
st.caption(
    "Live competitor research → side-by-side comparison → native-language voice note for the parent."
)

with st.form("compare_form"):
    col1, col2, col3 = st.columns([3, 2, 1.5])
    college_name = col1.text_input(
        "Competitor college", placeholder="e.g. CMR College of Engineering, Hyderabad"
    )
    parent_name = col2.text_input(
        "Parent name (optional)", placeholder="e.g. Ramesh garu"
    )
    language = col3.selectbox("Language", LANGUAGES)
    submitted = st.form_submit_button("Generate comparison", type="primary")

if submitted:
    if not college_name.strip():
        st.warning("Please enter a competitor college name.")
        st.stop()

    compare = compare_via_backend if BACKEND_URL else compare_in_process
    with st.spinner(
        f"Researching {college_name} and preparing a {language} voice note…"
    ):
        try:
            result, audio = compare(college_name, language, parent_name or None)
        except ComparisonError as exc:
            st.error(str(exc))
            st.stop()
    st.session_state["result"] = result
    st.session_state["audio"] = audio
    st.session_state["college"] = college_name

result = st.session_state.get("result")
if result:
    college = st.session_state["college"]
    audio = st.session_state.get("audio")

    st.subheader(f"About {college}")
    st.write(result["competitor_summary"])

    st.subheader("Side-by-side comparison")
    head_aspect, head_comp, head_niat = st.columns([1, 2, 2])
    head_aspect.markdown("**Aspect**")
    head_comp.markdown(f"**{college}**")
    head_niat.markdown("**NIAT**")
    for point in result["comparison_points"]:
        c_aspect, c_comp, c_niat = st.columns([1, 2, 2])
        c_aspect.markdown(f"**{point['aspect']}**")
        c_comp.write(point.get("competitor", "Not publicly available"))
        c_niat.success(point.get("niat", ""))

    st.subheader("Voice note for the parent")
    if audio:
        st.audio(audio, format="audio/mp3")
        st.download_button(
            "Download MP3",
            audio,
            file_name="niat_voice_note.mp3",
            mime="audio/mpeg",
        )
    else:
        st.info("Voice synthesis failed; the script is shown below.")

    with st.expander("Parent script (text)", expanded=not audio):
        st.write(result["parent_script_native"])

    if result.get("tools_called"):
        st.caption("Agent tools used: " + ", ".join(result["tools_called"]))
