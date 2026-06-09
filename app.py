import streamlit as st
import openai
import requests
import json
import base64
from datetime import datetime, timedelta

# =========================================================================
# SICHERHEITS-KONFIGURATION
# =========================================================================
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

USER_ID = "alex_soldat"
DEFAULT_SUBJECTS = ["Mathe", "Deutsch", "Englisch", "Geschichte", "Biologie", "Physik", "Chemie", "Geografie", "Informatik"]

st.set_page_config(page_title="StudyTutor 🐊", layout="wide", initial_sidebar_state="expanded")

# PREMIUM CUSTOM CSS (Optimiert für direkte Sichtbarkeit)
st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=300;400;500;600;700&display=swap');
    .stApp { background-color: #fafafa; color: #1e293b; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #f1f5f9; padding-top: 2rem; }
    .task-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border-left: 5px solid #ef4444;
    }
    .card-title { font-weight: 600; font-size: 1.1rem; color: #0f172a; margin-bottom: 4px; }
    .card-summary { font-size: 0.95rem; color: #1e293b; font-weight: 500; margin-bottom: 6px; }
    .card-info-line { font-size: 0.85rem; color: #e11d48; font-weight: 700; background: #ffe4e6; padding: 4px 8px; border-radius: 6px; display: inline-block; margin-bottom: 4px; }
    .card-date { font-size: 0.75rem; color: #94a3b8; font-weight: 500; }
    .column-header { font-size: 1.1rem; font-weight: 600; color: #334155; padding-bottom: 8px; margin-bottom: 16px; border-bottom: 2px solid #e2e8f0; }
    .subject-badge { background-color: #f1f5f9; color: #475569; padding: 6px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 500; margin-bottom: 6px; display: inline-block; border: 1px solid #e2e8f0; }
</style>
""")

# =========================================================================
# INTELLIGENTE DATUMS-LOGIK (Berechnet Wochentage & "Nächste Woche")
# =========================================================================
def parse_date_from_text(zeit_info):
    now = datetime.now()
    wochentage = {"montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3, "freitag": 4, "samstag": 5, "sonntag": 6}
    
    zeit_info_lower = zeit_info.lower()
    
    # Fall 1: "Nächste Woche" ohne genauen Tag -> Setze auf den nächsten Montag
    if "nächst" in zeit_info_lower and not any(tag in zeit_info_lower for tag in wochentage):
        tage_bis_montag = (0 - now.weekday() + 7) % 7
        if tage_bis_montag == 0: tage_bis_montag = 7
        ziel_datum = now + timedelta(days=tage_bis_montag)
        return f"Nächste Woche (ca. {ziel_datum.strftime('%d.%m.%Y')})"
        
    # Fall 2: Bestimmter Wochentag genannt (z.B. "Dienstag")
    for tag, index in wochentage.items():
        if tag in zeit_info_lower:
            tage_unterschied = (index - now.weekday() + 7) % 7
            if tage_unterschied == 0 and "nächst" in zeit_info_lower:
                tage_unterschied = 7
            elif tage_unterschied == 0:
                # Wenn heute Dienstag ist und man "Dienstag" sagt, meint man meistens heute oder nächsten
                tage_unterschied = 0 
                
            ziel_datum = now + timedelta(days=tage_unterschied)
            tag_name = tag.capitalize()
            
            if "nächst" in zeit_info_lower:
                return f"Nächsten {tag_name}, {ziel_datum.strftime('%d.%m.%Y')}"
            else:
                return f"Diesen {tag_name}, {ziel_datum.strftime('%d.%m.%Y')}"
                
    return zeit_info # Fallback, falls die KI etwas anderes geliefert hat

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
    except: pass
    return None

def save_to_supabase(state_data):
    if not state_data or "tasks" not in state_data: return
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

def extract_tasks_with_thinking(text, subjects_list):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""Analysiere den folgenden Schul-Text extrem gründlich.
        Verfügbare Fächer: {', '.join(subjects_list)}
        
        STRIKTE REGELN FÜR DIE SORTIERUNG:
        1. Wenn 'Test', 'Arbeit', 'Prüfung', 'Klausur' vorkommt -> Typ MUSS "Test" sein (Egal ob diese oder nächste Woche!).
        2. Wenn KEIN Test vorkommt, aber 'nächste Woche' oder 'Hausaufgabe' -> Typ ist "Nächste Woche".
        3. Wenn es ein 'Lernplan' ist -> Typ ist "Lernplan".
        
        Zusätzlich musst du genau heraushören, WANN das Ereignis stattfindet (z.B. "Dienstag", "nächste Woche", "Mittwoch"). Trage das exakt in das Feld "zeitpunkt" ein.
        
        Antworte NUR mit einer JSON-Liste von Objekten:
        [
          {{"title": "Fachname", "type": "Test" oder "Nächste Woche" oder "Lernplan", "summary": "Kurztitel", "zeitpunkt": "z.B. Dienstag oder nächste Woche oder Mittwoch"}}
        ]
        Text: "{text}" """
        
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.1)
        res_text = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        extracted_list = json.loads(res_text)
        
        tasks = []
        now_str = datetime.now().strftime("%d.%m.%Y")
        for item in extracted_list:
            raw_zeit = item.get("zeitpunkt", "Unbekannt")
            # Berechne das echte Datum aus dem Text
            echtes_datum = parse_date_from_text(raw_zeit)
            
            tasks.append({
                "title": item.get("title", "Allgemein"),
                "type": item.get("type", "Nächste Woche"),
                "summary": item.get("summary", "Neue Aufgabe"),
                "notes": text,
                "termin": echtes_datum, # Das berechnete, lesbare Datum direkt für die Karte!
                "erstellt_am": now_str,
                "id": f"{datetime.utcnow().timestamp()}_{item.get('title')}"
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
        st.session_state.messages = [{"role": "assistant", "content": "Hi! 🐊 Dein fehlerfreies Board mit Live-Terminen steht!"}]
        st.session_state.subjects = DEFAULT_SUBJECTS
    st.session_state.initialized = True

user_input = None

# AUDIO INPUT SIDEBAR
audio_file = st.sidebar.audio_input("🎙️ Sprachbefehl aufnehmen", key="main_audio_input")
if audio_file and st.sidebar.button("🚀 Sprachnachricht senden", use_container_width=True):
    text_from_speech = transcribe_audio(audio_file)
    if text_from_speech and text_from_speech.strip().lower() not in ["you", "you.", ""]:
        user_input = text_from_speech

# TEXT INPUT VERARBEITUNG
if user_input:
    new_tasks = extract_tasks_with_thinking(user_input, st.session_state.subjects)
    for task in new_tasks:
        if not any(t.get("title") == task["title"] and t.get("summary") == task["summary"] for t in st.session_state.tasks):
            st.session_state.tasks.insert(0, task)
    st.session_state.messages.append({"role": "user", "content": user_input})
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": "Bestätige kurz und sachlich die Eintragung."}, {"role": "user", "content": user_input}], temperature=0.2)
        st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
        save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
    except: pass
    st.rerun()

# SIDEBAR NAVIGATION
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
        save_to_supabase({"tasks": [], "messages": st.session_state.messages, "subjects": st.session_state.subjects})
        st.rerun()

# MAIN WORKSPACE
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

# SPALTE 1: TESTS
with col1:
    st.html("<div class='column-header'><span style='color: #ef4444;'>🔴</span> Tests & Arbeiten</div>")
    tests = [t for t in st.session_state.tasks if t.get("type") == "Test"]
    if not tests: st.caption("Keine Tests geplant. 🎉")
    for t in tests:
        # HIER WIRD DAS DATUM UND DER WOCHENTAG DIREKT ANGEZEIGT:
        st.html(f"""
        <div class='task-card' style='border-left-color: #ef4444;'>
            <div class='card-info-line'>📅 {t.get('termin', 'Kein Datum')}</div>
            <div class='card-title'>{t['title']}</div>
            <div class='card-summary'>{t['summary']}</div>
            <div class='card-date'>Notiert am: {t.get('erstellt_am')}</div>
        </div>
        """)
        with st.popover("Originaltext zeigen", use_container_width=True):
            st.info(t["notes"])

# SPALTE 2: NÄCHSTE WOCHE (Hier landen jetzt alle normalen Aufgaben für nächste Woche)
with col2:
    st.html("<div class='column-header'><span style='color: #f59e0b;'>🟡</span> Nächste Woche</div>")
    next_week = [t for t in st.session_state.tasks if t.get("type") == "Nächste Woche"]
    if not next_week: st.caption("Alles ruhig! 😎")
    for w in next_week:
        st.html(f"""
        <div class='task-card' style='border-left-color: #f59e0b;'>
            <div class='card-info-line' style='color:#b45309; background:#fef3c7;'>📅 {w.get('termin', 'Nächste Woche')}</div>
            <div class='card-title'>{w['title']}</div>
            <div class='card-summary'>{w['summary']}</div>
            <div class='card-date'>Notiert am: {w.get('erstellt_am')}</div>
        </div>
        """)
        with st.popover("Originaltext zeigen", use_container_width=True):
            st.info(w["notes"])

# SPALTE 3: LERNPLAN
with col3:
    st.html("<div class='column-header'><span style='color: #10b981;'>🟢</span> Aktivierter Lernplan</div>")
    plan = [t for t in st.session_state.tasks if t.get("type") == "Lernplan"]
    if not plan: st.caption("Kein aktiver Lernplan.")
    for p in plan:
        st.html(f"""
        <div class='task-card' style='border-left-color: #10b981;'>
            <div class='card-title'>{p['title']}</div>
            <div class='card-summary'>{p['summary']}</div>
        </div>
        """)
