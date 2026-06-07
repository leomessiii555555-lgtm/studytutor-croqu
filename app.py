import streamlit as st
import openai
import requests
import json
import base64
from datetime import datetime

# =========================================================================
# SICHERHEITS-KONFIGURATION
# =========================================================================
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

USER_ID = "alex_soldat"
DEFAULT_SUBJECTS = ["Mathe", "Deutsch", "Englisch", "Geschichte", "Biologie", "Physik", "Chemie", "Geografie", "Informatik"]

# Page Config für den echten App-Look
st.set_page_config(page_title="StudyTutor 🐊", layout="wide", initial_sidebar_state="expanded")

# INTERNATIONALE LERN-APP DESIGN-ENGINE (Premium Custom CSS)
st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Globales App-Styling */
    .stApp { background-color: #fafafa; color: #1e293b; font-family: 'Inter', sans-serif; }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #f1f5f9; padding-top: 2rem; }
    
    /* Moderne Kanban-Karten */
    .task-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s, box-shadow 0.2s;
        border-left: 5px solid #ef4444;
    }
    .task-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05); }
    .card-title { font-weight: 600; font-size: 1.05rem; color: #0f172a; margin-bottom: 4px; }
    .card-summary { font-size: 0.9rem; color: #64748b; font-weight: 400; }
    
    /* Column Headers */
    .column-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #334155;
        padding-bottom: 8px;
        margin-bottom: 16px;
        border-bottom: 2px solid #e2e8f0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Badges für die Fächer links */
    .subject-badge {
        background-color: #f1f5f9;
        color: #475569;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        margin-bottom: 6px;
        display: inline-block;
        border: 1px solid #e2e8f0;
    }
    
    /* Chat-Eingabe Feinschliff */
    div[data-testid="stChatInput"] { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }
</style>
""")

# =========================================================================
# ABSOLUT STABILES DB-SYSTEM
# =========================================================================
def load_from_supabase():
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{USER_ID}&select=app_state"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            data = response.json()[0].get('app_state')
            if data and isinstance(data, dict) and "tasks" in data:
                return data
    except:
        pass
    return None

def save_to_supabase(state_data):
    if not state_data or "tasks" not in state_data:
        return
    headers = {
        "apikey": SUPABASE_ANON_KEY, 
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data"
    payload = {"id": USER_ID, "app_state": state_data, "updated_at": datetime.utcnow().isoformat()}
    try:
        requests.post(url, headers=headers, json=payload)
    except:
        pass

def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.read()).decode("utf-8")

def transcribe_audio(audio_file):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        return transcript.text
    except:
        return None

def extract_task_with_ai(text, subjects_list):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""Analysiere diesen Schul-Text. Ordne ihn zwingend einem passenden Fach zu: {', '.join(subjects_list)}.
        (Korrgiere Abkürzungen: 'geo' -> 'Geografie', 'mathe' -> 'Mathe', 'bio' -> 'Biologie', 'deutsch' -> 'Deutsch').
        
        Bestimme den Typ ganz genau:
        - Wenn das Wort 'Test', 'Arbeit', 'Prüfung', 'Schularbeit' oder 'Ex' vorkommt -> IMMER 'Test'.
        - Wenn der User 'nächste Woche' oder 'Hausaufgabe' sagt -> 'Nächste Woche'.
        - Wenn es um einen Plan oder langfristiges Lernen geht -> 'Lernplan'.
        
        Antworte AUSSCHLIESSLICH mit einem gültigen JSON-Objekt, kein Markdown, keine Codeblocks:
        {{"title": "Fachname", "type": "Test" oder "Nächste Woche" oder "Lernplan", "summary": "Kurztitel max 4 Wörter"}}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        res_text = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        data = json.loads(res_text)
        return {
            "title": data.get("title", "Allgemein"),
            "type": data.get("type", "Nächste Woche"),
            "summary": data.get("summary", "Neue Aufgabe"),
            "notes": text,
            "id": str(datetime.utcnow().timestamp())
        }
    except:
        return {"title": "Aufgabe", "type": "Nächste Woche", "summary": "Neue Aufgabe", "notes": text, "id": str(datetime.utcnow().timestamp())}

# Safe Initialisierung
if "initialized" not in st.session_state:
    db_state = load_from_supabase()
    if db_state:
        st.session_state.tasks = db_state.get("tasks", [])
        st.session_state.messages = db_state.get("messages", [])
        st.session_state.subjects = db_state.get("subjects", DEFAULT_SUBJECTS)
    else:
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Hi! 🐊 Dein fehlerfreier Premium-Workspace steht. Sprich oder schreib mir einfach!"}]
        st.session_state.subjects = DEFAULT_SUBJECTS
    st.session_state.initialized = True

user_input = None

# =========================================================================
# FRÜHZEITIGE EINGABE-ERFASSUNG (BEHEBT DAS EINTRAGUNGS-PROBLEM)
# =========================================================================
# 1. Audio-Input Check
audio_file = st.sidebar.audio_input("🎙️ Sprachbefehl aufnehmen", key="main_audio_input")
if audio_file:
    if st.sidebar.button("🚀 Sprachnachricht senden", use_container_width=True):
        text_from_speech = transcribe_audio(audio_file)
        if text_from_speech and text_from_speech.strip().lower() not in ["you", "you.", ""]:
            user_input = text_from_speech

# 2. Text-Input Check (unten platziert, aber Variable oben abgefangen)
# (Der eigentliche Chat-Input-Call befindet sich weiter unten im Code)

# Sofortige Verarbeitung, wenn eine Eingabe (Text oder Sprache) vorliegt
if user_input:
    # DUPLIKAT-SCHUTZ: Prüfen, ob die exakt gleiche Notiz schon existiert
    is_duplicate = any(t.get("notes", "").strip().lower() == user_input.strip().lower() for t in st.session_state.tasks)
    
    if not is_duplicate:
        new_task = extract_task_with_ai(user_input, st.session_state.subjects)
        if new_task:
            st.session_state.tasks.insert(0, new_task)
            
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        sys_prompt = f"Du bist ein minimalistischer KI-Lerncoach. Antworte in maximal 2 Sätzen. Bestätige kurz, dass die Aufgabe einsortiert wurde. Aktuelle Liste: {json.dumps(st.session_state.tasks)}"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_input}],
            temperature=0.2
        )
        ai_answer = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": ai_answer})
        
        # Direkt in Supabase absichern
        save_to_supabase({
            "tasks": st.session_state.tasks, 
            "messages": st.session_state.messages,
            "subjects": st.session_state.subjects
        })
    except:
        pass
    st.rerun()

# =========================================================================
# SIDEBAR UI
# =========================================================================
with st.sidebar:
    st.title("StudyTutor 🐊")
    st.write("---")
    
    st.subheader("📚 Meine Fächer")
    for sub in st.session_state.subjects:
        count = len([t for t in st.session_state.tasks if t.get("title").lower() == sub.lower()])
        badge_text = f"{sub} ({count})" if count > 0 else sub
        st.html(f"<div class='subject-badge'>{badge_text}</div>")
        
    st.write("---")
    
    with st.expander("⚙️ System-Tools"):
        uploaded_image = st.file_uploader("Stundenplan einscannen", type=["jpg", "jpeg", "png"])
        if uploaded_image and st.button("Fächer aktualisieren"):
            with st.spinner("Lese Fächer..."):
                try:
                    base64_image = encode_image(uploaded_image)
                    client = openai.OpenAI(api_key=OPENAI_API_KEY)
                    img_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": [{"type": "text", "text": "Extrahiere Schulfächer als kommagetrennte Liste."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}]
                    )
                    st.session_state.subjects = [s.strip() for s in img_response.choices[0].message.content.split(",") if s.strip()]
                    save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
                    st.rerun()
                except:
                    pass
        if st.button("🗑️ App komplett zurücksetzen"):
            st.session_state.tasks = []
            st.session_state.messages = [{"role": "assistant", "content": "App wurde zurückgesetzt."}]
            save_to_supabase({"tasks": [], "messages": st.session_state.messages, "subjects": st.session_state.subjects})
            st.rerun()

# =========================================================================
# RECHTER HAUPTBEREICH: DAS RESPONSIVE KANBAN-BOARD
# =========================================================================

# Sektion 1: Der edle Chat-Bereich (kompakt auf die letzten 3 Nachrichten limitiert)
with st.expander("💬 KI-Lerncoach Chatverlauf", expanded=True):
    for msg in st.session_state.messages[-3:]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    if text_input := st.chat_input("Schreib eine neue Aufgabe (z.B. 'Mathe Test am Freitag')..."):
        # Setzt die Variable für die Verarbeitung ganz oben und triggert einen Rerun
        st.session_state["text_processing_input"] = text_input
        
if "text_processing_input" in st.session_state:
    user_input = st.session_state.pop("text_processing_input")
    is_duplicate = any(t.get("notes", "").strip().lower() == user_input.strip().lower() for t in st.session_state.tasks)
    if not is_duplicate:
        new_task = extract_task_with_ai(user_input, st.session_state.subjects)
        if new_task:
            st.session_state.tasks.insert(0, new_task)
    st.session_state.messages.append({"role": "user", "content": user_input})
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        sys_prompt = f"Du bist ein minimalistischer KI-Lerncoach. Antworte in maximal 2 Sätzen. Bestätige kurz die Eintragung. Liste: {json.dumps(st.session_state.tasks)}"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_input}],
            temperature=0.2
        )
        st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
        save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
    except:
        pass
    st.rerun()

# Sektion 2: Das professionelle Kanban Board (Die 3 Spalten nebeneinander)
st.write("### 📊 Mein aktueller Workspace")
col1, col2, col3 = st.columns(3)

# SPALTE 1: TESTS
with col1:
    st.html("<div class='column-header'><span style='color: #ef4444;'>🔴</span> Tests & Arbeiten</div>")
    tests = [t for t in st.session_state.tasks if t.get("type") == "Test"]
    if not tests:
        st.caption("Keine Tests geplant. 🎉")
    for t in tests:
        st.html(f"<div class='task-card' style='border-left-color: #ef4444;'><div class='card-title'>{t['title']}</div><div class='card-summary'>{t['summary']}</div></div>")
        with st.popover("Details öffnen", use_container_width=True):
            st.write(f"**Ganzes Sprachprotokoll:** {t['notes']}")

# SPALTE 2: NÄCHSTE WOCHE
with col2:
    st.html("<div class='column-header'><span style='color: #f59e0b;'>🟡</span> Nächste Woche</div>")
    next_week = [t for t in st.session_state.tasks if t.get("type") == "Nächste Woche"]
    if not next_week:
        st.caption("Alles ruhig für die nächste Woche! 😎")
    for w in next_week:
        st.html(f"<div class='task-card' style='border-left-color: #f59e0b;'><div class='card-title'>{w['title']}</div><div class='card-summary'>{w['summary']}</div></div>")
        with st.popover("Details öffnen", use_container_width=True):
            st.write(f"**Ganzes Sprachprotokoll:** {w['notes']}")

# SPALTE 3: LERNPLAN
with col3:
    st.html("<div class='column-header'><span style='color: #10b981;'>🟢</span> Aktivierter Lernplan</div>")
    plan = [t for t in st.session_state.tasks if t.get("type") == "Lernplan"]
    if not plan:
        st.caption("Kein aktiver Lernplan.")
    for p in plan:
        st.html(f"<div class='task-card' style='border-left-color: #10b981;'><div class='card-title'>{p['title']}</div><div class='card-summary'>{p['summary']}</div></div>")
        with st.popover("Details öffnen", use_container_width=True):
            st.write(f"**Ganzes Sprachprotokoll:** {p['notes']}")
