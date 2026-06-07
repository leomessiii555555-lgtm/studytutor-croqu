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

st.set_page_config(page_title="StudyTutor 🐊", layout="wide", initial_sidebar_state="expanded")

# PREMIUM CUSTOM CSS
st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp { background-color: #fafafa; color: #1e293b; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #f1f5f9; padding-top: 2rem; }
    .task-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border-left: 5px solid #ef4444;
    }
    .card-title { font-weight: 600; font-size: 1.05rem; color: #0f172a; margin-bottom: 4px; }
    .card-summary { font-size: 0.9rem; color: #64748b; }
    .column-header { font-size: 1.1rem; font-weight: 600; color: #334155; padding-bottom: 8px; margin-bottom: 16px; border-bottom: 2px solid #e2e8f0; }
    .subject-badge { background-color: #f1f5f9; color: #475569; padding: 6px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 500; margin-bottom: 6px; display: inline-block; border: 1px solid #e2e8f0; }
    
    /* Fokusmodus Container */
    .focus-container {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 32px;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05);
        margin-top: 20px;
    }
</style>
""")

# =========================================================================
# DB-SYSTEM
# =========================================================================
def load_from_supabase():
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{USER_ID}&select=app_state"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0].get('app_state')
    except:
        pass
    return None

def save_to_supabase(state_data):
    if not state_data or "tasks" not in state_data:
        return
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data"
    payload = {"id": USER_ID, "app_state": state_data, "updated_at": datetime.utcnow().isoformat()}
    try: requests.post(url, headers=headers, json=payload)
    except: pass

def transcribe_audio(audio_file):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        audio_data = audio_file.read()
        if not audio_data: return None
        transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_data, "audio/wav"))
        return transcript.text
    except: return None

# KI ERZWINGT SCHRITT-FÜR-SCHRITT NACHDENKEN & GENERIERT STRUKTURIERTE LERNPLÄNE
def extract_tasks_with_thinking(text, subjects_list):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""Du bist das Gehirn einer intelligenten Lern-App. Analysiere den folgenden Text extrem gründlich.
        Verfügbare Fächer: {', '.join(subjects_list)} (Abkürzungen wie 'geo', 'mathe' korrigieren).
        
        SCHRITT-FÜR-SCHRITT-ANALYSE:
        1. Enthält der Text mehrere Aufgaben/Tests? Trenne sie auf.
        2. Bestimme für jede Aufgabe den Typ:
           - Wenn 'Test', 'Arbeit', 'Prüfung', 'Klausur' vorkommt -> "Test".
           - Wenn es explizit um einen Plan, Vorbereitung über mehrere Tage oder das Wort 'Lernplan' geht -> "Lernplan".
           - Ansonsten -> "Nächste Woche".
        3. WICHTIG - Wenn der Typ "Lernplan" ist: Generiere im Feld "notes" einen ausführlichen, professionellen, formatierten Schritt-für-Schritt Lernplan in Markdown (mit Meilensteinen, Tag 1, Tag 2, Tipps). Kopiere NIEMALS einfach nur den Satz des Users!
        
        Antworte AUSSCHLIESSLICH mit einer JSON-Liste von Objekten. Kein Markdown um das JSON herum!
        Format:
        [
          {{"title": "Fachname", "type": "Test" oder "Nächste Woche" oder "Lernplan", "summary": "Kurztitel max 4 Wörter", "notes": "Hier entweder der Originaltext ODER der ausführlich generierte Lernplan"}}
        ]
        
        Text zum Analysieren: "{text}" """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        res_text = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        extracted_list = json.loads(res_text)
        
        tasks = []
        for item in extracted_list:
            tasks.append({
                "title": item.get("title", "Allgemein"),
                "type": item.get("type", "Nächste Woche"),
                "summary": item.get("summary", "Neue Aufgabe"),
                "notes": item.get("notes", text),
                "id": f"{datetime.utcnow().timestamp()}_{item.get('title')}",
                "chat_history": [] # Jede Aufgabe bekommt ihren eigenen isolierten Chatverlauf!
            })
        return tasks
    except: return []

# Initialisierung
if "initialized" not in st.session_state:
    db_state = load_from_supabase()
    if db_state:
        st.session_state.tasks = db_state.get("tasks", [])
        st.session_state.messages = db_state.get("messages", [])
        st.session_state.subjects = db_state.get("subjects", DEFAULT_SUBJECTS)
    else:
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Hi! 🐊 Dein Workspace denkt jetzt intelligent mit."}]
        st.session_state.subjects = DEFAULT_SUBJECTS
    st.session_state.active_task_id = None # Speichert, ob wir gerade im Vollbild-Modus einer Aufgabe sind
    st.session_state.initialized = True

user_input = None

# AUDIO INPUT SIDEBAR
audio_file = st.sidebar.audio_input("🎙️ Sprachbefehl aufnehmen", key="main_audio_input")
if audio_file and st.sidebar.button("🚀 Sprachnachricht senden", use_container_width=True):
    text_from_speech = transcribe_audio(audio_file)
    if text_from_speech and text_from_speech.strip().lower() not in ["you", "you.", ""]:
        user_input = text_from_speech

if user_input:
    new_tasks = extract_tasks_with_thinking(user_input, st.session_state.subjects)
    for task in new_tasks:
        if not any(t.get("title") == task["title"] and t.get("summary") == task["summary"] for t in st.session_state.tasks):
            st.session_state.tasks.insert(0, task)
    st.session_state.messages.append({"role": "user", "content": user_input})
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": "Bestätige kurz und smart die Eintragung."}, {"role": "user", "content": user_input}], temperature=0.2)
        st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
        save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
    except: pass
    st.rerun()

# SIDEBAR NAVIGATION & FACHER
with st.sidebar:
    st.title("StudyTutor 🐊")
    st.write("---")
    st.subheader("📚 Meine Fächer")
    for sub in st.session_state.subjects:
        count = len([t for t in st.session_state.tasks if t.get("title").lower() == sub.lower()])
        st.html(f"<div class='subject-badge'>{sub} ({count})" if count > 0 else f"<div class='subject-badge'>{sub}</div>")
    st.write("---")
    if st.button("🗑️ App komplett zurücksetzen"):
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Zurückgesetzt."}]
        st.session_state.active_task_id = None
        save_to_supabase({"tasks": [], "messages": st.session_state.messages, "subjects": st.session_state.subjects})
        st.rerun()

# =========================================================================
# DYNAMISCHER WORKSPACE (DASHBOARD ODER VOLLBILD-FOKUSMODUS)
# =========================================================================

if st.session_state.active_task_id is not None:
    # ---------------------------------------------------------------------
    # NEU: DAS GANZE NEUE FENSTER (FOKUSMODUS FÜR LERNPLAN & DETAILS)
    # ---------------------------------------------------------------------
    selected_task = next((t for t in st.session_state.tasks if t["id"] == st.session_state.active_task_id), None)
    
    if selected_task:
        if st.button("← Zurück zum Workspace / Dashboard", type="secondary"):
            st.session_state.active_task_id = None
            st.rerun()
            
        st.html(f"<div class='focus-container'><h2>📖 {selected_task['title']} - Fokusmodus</h2><p style='color:gray;'>Typ: {selected_task['type']}</p></div>")
        
        col_plan, col_chat = st.columns([7, 5])
        
        with col_plan:
            st.write("### 📝 Inhalt & Lernplan")
            st.markdown(selected_task["notes"])
            
        with col_chat:
            st.write("### 🤖 Fragen zu diesem Lernplan?")
            
            # Eigener, isolierter Chatverlauf nur für diese eine Aufgabe!
            if "chat_history" not in selected_task:
                selected_task["chat_history"] = []
                
            for c_msg in selected_task["chat_history"]:
                with st.chat_message(c_msg["role"]):
                    st.write(c_msg["content"])
                    
            if task_chat_input := st.chat_input("Stelle dem KI-Coach eine Frage zu diesem Plan...", key="task_chat"):
                selected_task["chat_history"].append({"role": "user", "content": task_chat_input})
                
                with st.spinner("Überlege..."):
                    try:
                        client = openai.OpenAI(api_key=OPENAI_API_KEY)
                        task_prompt = f"Du bist ein persönlicher Lerncoach. Beziehe dich ausschließlich auf diesen aktuellen Lernplan:\n{selected_task['notes']}\n\nFrage des Schülers: {task_chat_input}"
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": task_prompt}]
                        )
                        selected_task["chat_history"].append({"role": "assistant", "content": response.choices[0].message.content})
                        save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
                    except: pass
                st.rerun()
    else:
        st.session_state.active_task_id = None
        st.rerun()

else:
    # ---------------------------------------------------------------------
    # DAS NORMALES DASHBOARD (WENN KEIN FOKUSMODUS AKTIV IST)
    # ---------------------------------------------------------------------
    with st.expander("💬 KI-Lerncoach Chatverlauf", expanded=True):
        for msg in st.session_state.messages[-3:]:
            with st.chat_message(msg["role"]): st.write(msg["content"])
        if text_input := st.chat_input("Schreib deine Aufgaben hier hinein..."):
            st.session_state["text_processing_input"] = text_input
            
    if "text_processing_input" in st.session_state:
        user_input = st.session_state.pop("text_processing_input")
        new_tasks = extract_tasks_with_thinking(user_input, st.session_state.subjects)
        for task in new_tasks:
            if not any(t.get("title") == task["title"] and t.get("summary") == task["summary"] for t in st.session_state.tasks):
                st.session_state.tasks.insert(0, task)
        st.session_state.messages.append({"role": "user", "content": user_input})
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": "Bestätige kurz die Eintragung."}, {"role": "user", "content": user_input}], temperature=0.2)
            st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
            save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
        except: pass
        st.rerun()

    st.write("### 📊 Mein aktueller Workspace")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.html("<div class='column-header'><span style='color: #ef4444;'>🔴</span> Tests & Arbeiten</div>")
        tests = [t for t in st.session_state.tasks if t.get("type") == "Test"]
        if not tests: st.caption("Keine Tests geplant. 🎉")
        for t in tests:
            st.html(f"<div class='task-card' style='border-left-color: #ef4444;'><div class='card-title'>{t['title']}</div><div class='card-summary'>{t['summary']}</div></div>")
            if st.button("Ansehen & Chatten", key=f"view_{t['id']}", use_container_width=True):
                st.session_state.active_task_id = t["id"]
                st.rerun()

    with col2:
        st.html("<div class='column-header'><span style='color: #f59e0b;'>🟡</span> Nächste Woche</div>")
        next_week = [t for t in st.session_state.tasks if t.get("type") == "Nächste Woche"]
        if not next_week: st.caption("Alles ruhig! 😎")
        for w in next_week:
            st.html(f"<div class='task-card' style='border-left-color: #f59e0b;'><div class='card-title'>{w['title']}</div><div class='card-summary'>{w['summary']}</div></div>")
            if st.button("Ansehen & Chatten", key=f"view_{w['id']}", use_container_width=True):
                st.session_state.active_task_id = w["id"]
                st.rerun()

    with col3:
        st.html("<div class='column-header'><span style='color: #10b981;'>🟢</span> Aktivierter Lernplan</div>")
        plan = [t for t in st.session_state.tasks if t.get("type") == "Lernplan"]
        if not plan: st.caption("Kein aktiver Lernplan.")
        for p in plan:
            st.html(f"<div class='task-card' style='border-left-color: #10b981;'><div class='card-title'>{p['title']}</div><div class='card-summary'>{p['summary']}</div></div>")
            if st.button("Lernplan öffnen 🚀", key=f"view_{p['id']}", use_container_width=True):
                st.session_state.active_task_id = p["id"]
                st.rerun()
