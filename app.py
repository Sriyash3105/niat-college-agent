"""Streamlit counselor portal for the NIAT Compare My College agent."""

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
LANGUAGES = ["Telugu", "Hindi", "Tamil", "English"]

st.set_page_config(page_title="NIAT · Compare My College", page_icon="🎓", layout="wide")
st.title("🎓 Compare My College")
st.caption("Live competitor research → side-by-side comparison → native-language voice note for the parent.")

with st.form("compare_form"):
    col1, col2, col3 = st.columns([3, 2, 1.5])
    college_name = col1.text_input("Competitor college", placeholder="e.g. CMR College of Engineering, Hyderabad")
    parent_name = col2.text_input("Parent name (optional)", placeholder="e.g. Ramesh garu")
    language = col3.selectbox("Language", LANGUAGES)
    submitted = st.form_submit_button("Generate comparison", type="primary")

if submitted:
    if not college_name.strip():
        st.warning("Please enter a competitor college name.")
        st.stop()

    with st.spinner(f"Researching {college_name} and preparing a {language} voice note…"):
        try:
            resp = requests.post(
                f"{BACKEND_URL}/compare",
                json={"college_name": college_name, "language": language, "parent_name": parent_name or None},
                timeout=180,
            )
            resp.raise_for_status()
            st.session_state["result"] = resp.json()
            st.session_state["college"] = college_name
        except requests.HTTPError:
            st.error(f"Backend error: {resp.text}")
            st.stop()
        except requests.RequestException as exc:
            st.error(f"Could not reach backend at {BACKEND_URL}: {exc}")
            st.stop()

result = st.session_state.get("result")
if result:
    college = st.session_state["college"]

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
        c_comp.write(point["competitor"])
        c_niat.success(point["niat"])

    st.subheader("Voice note for the parent")
    if result.get("audio_url"):
        # Fetch bytes server-side so this works even when the backend isn't publicly reachable.
        try:
            audio = requests.get(f"{BACKEND_URL}{result['audio_url']}", timeout=30)
            audio.raise_for_status()
            st.audio(audio.content, format="audio/mp3")
            st.download_button("Download MP3", audio.content, file_name="niat_voice_note.mp3", mime="audio/mpeg")
        except requests.RequestException as exc:
            st.error(f"Could not load audio: {exc}")
    else:
        st.info("Voice synthesis failed; the script is shown below.")

    with st.expander("Parent script (text)", expanded=not result.get("audio_url")):
        st.write(result["parent_script_native"])

    if result.get("tools_called"):
        st.caption("Agent tools used: " + ", ".join(result["tools_called"]))
