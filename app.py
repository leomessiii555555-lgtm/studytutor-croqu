import streamlit as st
import openai
import requests
import json
import re
from datetime import datetime, timedelta

# =========================================================================
# SICHERHEITS-KONFIGURATION & CLIENTS
# =========================================================================
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

client = openai.OpenAI(api_key=OPENAI_API_KEY)

USER_ID = "alex_soldat"
DEFAULT_SUBJECTS = ["Mathe", "Deutsch", "Englisch", "Geschichte", "Biologie", "Physik", "Chemie", "Geografie", "Informatik"]

st.set_page_config(page_title="StudyTutor 🐊", layout="wide", initial_sidebar_state="expanded")

# PREMIUM CUSTOM CSS
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
# INTELLIGENTE DATUMS-LOGIK
# =========================================================================
def parse_date_from_text(zeit_info):
    now = datetime.now()
    wochentage = {"montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3, "freitag": 4, "samstag": 5, "sonntag": 6}
    zeit_info_lower = zeit_info.lower()
    
    # Erkennung von exakten Daten im Text wie "6.7" oder "06.07."
    match = re.search(r'(\d{1,2})\.(\d{1,2})', zeit_info_lower)
    if match:
        tag = int(match.group(1))
        monat = int(match.group(2))
        try:
            ziel_datum = datetime(now.year, monat, tag)
            # Falls das Datum in der Vergangenheit liegt, nimm das nächste Jahr
            if ziel_datum < now.replace(hour=0, minute=0, second=0, microsecond=0):
                ziel_datum = datetime(now.year + 1, monat, tag)
            return ziel_datum.strftime('%d.%m.%Y')
        except ValueError:
            pass

    if "übermorgen" in zeit_info_lower:
        ziel_datum = now + timedelta(days=2)
        return f"Übermorgen, {ziel_datum.strftime('%d.%m.%Y')}"
        
    if "morgen" in zeit_info_lower:
        ziel_datum = now + timedelta(days=1)
        return f"Morgen, {ziel_datum.strftime('%d.%m.%Y')}"

    if "nächst" in zeit_info_lower and not any(tag in zeit_info_lower for tag in wochentage):
        tage_bis_montag = (0 - now.weekday() + 7) % 7
        if tage_bis_montag == 0: tage_bis_montag = 7
        ziel_datum = now + timedelta(days=tage_bis_montag)
        return f"Nächste Woche (ca. {ziel_datum.strftime('%d.%m.%Y')})"
        
    for tag, index in wochentage.items():
        if tag in zeit_info_lower:
            tage_unterschied = (index - now.weekday() + 7) % 7
            if tage_unterschied == 0 and "nächst" in zeit_info_lower:
                tage_unterschied = 7
            elif tage_unterschied == 0:
                tage_unterschied = 0 
                
            ziel_datum = now + timedelta(days=tage_unterschied)
            tag_name = tag.capitalize()
            
            if "nächst" in zeit_info_lower:
                return f"Nächsten {tag_name}, {ziel_datum.strftime('%d.%m.%Y')}"
            else:
                return f"Diesen {tag_name}, {ziel_datum.strftime('%d.%m.%Y')}"
                
    return zeit_info

# Hilfsfunktion um zu prüfen, ob ein Termin innerhalb der nächsten 14 Tage liegt
def is_within_next_fortnight(termin_str):
    if not termin_str:
        return False
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    max_date = now + timedelta(days=14)
    
    # Suche nach einem DD.MM.YYYY Format im String
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', termin_str)
    if match:
        try:
            task_date = datetime.strptime(match.group(0), '%d.%m.%Y')
            return now <= task_date <= max_date
        except ValueError:
            return False
            
    # Fallback für relative Angaben
    termin_lower = termin_str.lower()
    if "diesen" in termin_lower or "morgen" in termin_lower or "übermorgen" in termin_lower or "nächst" in termin_lower:
        return True
        
    return False

# =========================================================================
# DB-SYSTEM & API LOGIK
# =========================================================================
def load_from_supabase():
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{USER_ID}&select=app_state"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0].get('app_state')
    except Exception as e:
        st.sidebar.error(f"Fehler beim Laden: {e}")
    return None

def save_to_supabase(state_data):
    if not state_data or "tasks" not in state_data: return
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data"
    payload = {"id": USER_ID, "app_state": state_data, "updated_at": datetime.utcnow().isoformat()}
    try: 
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")

def transcribe_audio(audio_file):
    try:
        audio_data = audio_file.read()
        if not audio_data: return None
        transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_data, "audio/wav"))
        return transcript.text
    except Exception as e: 
        st.error(f"Audio-Fehler: {e}")
        return None

def extract_tasks_with_thinking(text, subjects_list):
    try:
        prompt = f"""Analysiere den folgenden Schul-Text extrem gründlich.
        Verfügbare Fächer: {', '.join(subjects_list)}
        
        STRIKTE REGELN FÜR DIE SORTIERUNG:
        1. Wenn 'Test', 'Arbeit', 'Prüfung', 'Klausur', 'Schularbeit' vorkommt -> Typ MUSS "Test" sein.
        2. Wenn es ein 'Lernplan' ist -> Typ ist "Lernplan".
        3. Ansonsten -> Typ ist "Hausaufgabe".
        
        Zusätzlich musst du genau heraushören, WANN das Ereignis stattfindet (z.B. "Dienstag", "6.7.", "nächste Woche"). Trage das exakt in das Feld "zeitpunkt" ein.
        
        Antworte NUR mit einer JSON-Liste von Objekten:
        [
          {{"title": "Fachname", "type": "Test" oder "Hausaufgabe" oder "Lernplan", "summary": "Kurztitel", "zeitpunkt": "z.B. 6.7."}}
        ]
        Text: "{text}" """
        
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.1)
        res_text = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        extracted_list = json.loads(res_text)
        
        tasks = []
        now_str = datetime.now().strftime("%d.%m.%Y")
        for item in extracted_list:
            raw_zeit = item.get("zeitpunkt", "Unbekannt")
            echtes_datum = parse_date_from_text(raw_zeit)
            
            tasks.append({
                "title": item.get("title", "Allgemein"),
                "type": item.get("type", "Hausaufgabe"),
                "summary": item.get("summary", "Neue Aufgabe"),
                "notes": text,
                "termin": echtes_datum, 
                "erstellt_am": now_str,
                "id": f"{datetime.utcnow().timestamp()}_{item.get('title')}"
            })
        return tasks
    except Exception as e: 
        st.error(f"Fehler bei KI-Extraktion: {e}")
        return []

def process_user_input(input_text):
    if not input_text or input_text.strip().lower() in ["you", "you.", ""]:
        return

    new_tasks = extract_tasks_with_thinking(input_text, st.session_state.subjects)
    for task in new_tasks:
        if not any(t.get("title") == task["title"] and t.get("summary") == task["summary"] for t in st.session_state.tasks):
            st.session_state.tasks.insert(0, task)
            
    st.session_state.messages.append({"role": "user", "content": input_text})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[
                {"role": "system", "content": "Bestätige kurz und sachlich die Eintragung."}, 
                {"role": "user", "content": input_text}
            ], 
            temperature=0.2
        )
        st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
        save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
    except Exception as e: 
        st.error(f"Fehler bei KI-Antwort: {e}")
        
    st.rerun()

# =========================================================================
# INITIALISIERUNG
# =========================================================================
if "initialized" not in st.session_state:
    db_state = load_from_supabase()
    if db_state:
        st.session_state.tasks = db_state.get("tasks", [])
        st.session_state.messages = db_state.get("messages", [])
        st.session_state.subjects = db_state.get("subjects", DEFAULT_SUBJECTS)
    else:
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Hi! 🐊 Dein Board mit Live-Terminen steht!"}]
        st.session_state.subjects = DEFAULT_SUBJECTS
    st.session_state.initialized = True

# AUDIO INPUT
audio_file = st.sidebar.audio_input("🎙️ Sprachbefehl aufnehmen", key="main_audio_input")
if audio_file and st.sidebar.button("🚀 Sprachnachricht senden", use_container_width=True):
    text_from_speech = transcribe_audio(audio_file)
    if text_from_speech:
        process_user_input(text_from_speech)

# SIDEBAR
with st.sidebar:
    st.title("StudyTutor 🐊")
    st.write("---")
    st.subheader("📚 Meine Fächer")
    for sub in st.session_state.subjects:
        count = len([t for t in st.session_state.tasks if t.get("title", "").lower() == sub.lower()])
        st.html(f"<div class='subject-badge'>{sub} ({count})</div>" if count > 0 else f"<div class='subject-badge'>{sub}</div>")
    st.write("---")
    if st.button("🗑️ App komplett zurücksetzen", use_container_width=True):
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Zurückgesetzt."}]
        save_to_supabase({"tasks": [], "messages": st.session_state.messages, "subjects": st.session_state.subjects})
        st.rerun()

# CHAT
with st.expander("💬 KI-Lerncoach Chatverlauf", expanded=True):
    for msg in st.session_state.messages[-3:]:
        with st.chat_message(msg["role"]): 
            st.write(msg["content"])
            
    if text_input := st.chat_input("Schreib deine Aufgaben hier hinein..."):
        process_user_input(text_input)

# =========================================================================
# LIVE WORKSPACE (MIT INTELLIGENTER TIMELINE-FILTERUNG)
# =========================================================================
st.write("### 📊 Mein aktueller Workspace")
col1, col2, col3 = st.columns(3)

# SPALTE 1: ALLE TESTS & ARBEITEN
with col1:
    st.html("<div class='column-header'><span style='color: #ef4444;'>🔴</span> Tests & Arbeiten</div>")
    tests = [t for t in st.session_state.tasks if t.get("type") == "Test"]
    if not tests: st.caption("Keine Tests geplant. 🎉")
    for t in tests:
        st.html(f"""
        <div class='task-card' style='border-left-color: #ef4444;'>
            <div class='card-info-line'>📅 {t.get('termin', 'Kein Datum')}</div>
            <div class='card-title'>{t['title']}</div>
            <div class='card-summary'>{t['summary']}</div>
            <div class='card-date'>Notiert am: {t.get('erstellt_am')}</div>
        </div>
        """)
        with st.popover("Originaltext", use_container_width=True): st.info(t["notes"])

# SPALTE 2: DYNAMISCHE TIMELINE (Zeigt NUR Einträge der nächsten 14 Tage!)
with col2:
    st.html("<div class='column-header'><span style='color: #f59e0b;'>🟡</span> Diese & Nächste Woche</div>")
    
    # Filtert strikt: Nur Aufgaben/Tests, deren errechnetes Datum innerhalb der nächsten 14 Tage liegt
    upcoming_tasks = [
        t for t in st.session_state.tasks 
        if t.get("type") in ["Hausaufgabe", "Test"] and is_within_next_fortnight(t.get("termin", ""))
    ]
    
    # Sortierung: Aktuelle Woche ("Diesen", "Morgen", "Übermorgen") nach oben
    upcoming_tasks.sort(key=lambda x: 0 if any(k in str(x.get("termin", "")).lower() for k in ["diesen", "morgen", "übermorgen"]) else 1)
    
    if not upcoming_tasks: st.caption("In den nächsten zwei Wochen steht nichts an! 😎")
    for w in upcoming_tasks:
        is_test = w.get("type") == "Test"
        card_color = "#ef4444" if is_test else "#f59e0b"
        title_prefix = "⚠️ TEST | " if is_test else "📝 HÜ | "
        
        st.html(f"""
        <div class='task-card' style='border-left-color: {card_color};'>
            <div class='card-info-line' style='color:#b45309; background:#fef3c7;'>📅 {w.get('termin', 'Unbekannt')}</div>
            <div class='card-title'>{title_prefix}{w['title']}</div>
            <div class='card-summary'>{w['summary']}</div>
            <div class='card-date'>Notiert am: {w.get('erstellt_am')}</div>
        </div>
        """)
        with st.popover("Originaltext", use_container_width=True): st.info(w["notes"])

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
