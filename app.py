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

st.set_page_config(page_title="StudyTutor Pro 🐊", layout="wide", initial_sidebar_state="expanded")

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
        margin-bottom: 4px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border-left: 5px solid #ef4444;
    }
    .card-title { font-weight: 600; font-size: 1.1rem; color: #0f172a; margin-bottom: 4px; }
    .card-summary { font-size: 0.95rem; color: #1e293b; font-weight: 500; margin-bottom: 6px; }
    .card-info-line { font-size: 0.85rem; color: #e11d48; font-weight: 700; background: #ffe4e6; padding: 4px 8px; border-radius: 6px; display: inline-block; margin-bottom: 4px; }
    .column-header { font-size: 1.1rem; font-weight: 600; color: #334155; padding-bottom: 8px; margin-bottom: 16px; border-bottom: 2px solid #e2e8f0; }
    .subject-badge { background-color: #f1f5f9; color: #475569; padding: 6px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 500; margin-bottom: 6px; display: inline-block; border: 1px solid #e2e8f0; }
    .countdown-badge { font-size: 0.8rem; font-weight: 600; color: #dc2626; margin-top: 4px; display: flex; align-items: center; gap: 4px; }
</style>
""")

# =========================================================================
# INTELLIGENTE DATUMS- & COUNTDOWN-LOGIK
# =========================================================================
def parse_date_from_text(zeit_info):
    now = datetime.now()
    wochentage = {"montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3, "freitag": 4, "samstag": 5, "sonntag": 6}
    zeit_info_lower = str(zeit_info).lower()
    
    match = re.search(r'(\d{1,2})\.(\d{1,2})', zeit_info_lower)
    if match:
        tag = int(match.group(1))
        monat = int(match.group(2))
        try:
            ziel_datum = datetime(now.year, monat, tag)
            if ziel_datum < now.replace(hour=0, minute=0, second=0, microsecond=0):
                ziel_datum = datetime(now.year + 1, monat, tag)
            return ziel_datum.strftime('%d.%m.%Y')
        except ValueError: pass

    if "übermorgen" in zeit_info_lower: return (now + timedelta(days=2)).strftime('%d.%m.%Y')
    if "morgen" in zeit_info_lower: return (now + timedelta(days=1)).strftime('%d.%m.%Y')

    for tag, index in wochentage.items():
        if tag in zeit_info_lower:
            tage_unterschied = (index - now.weekday() + 7) % 7
            if tage_unterschied == 0 and "nächst" in zeit_info_lower: tage_unterschied = 7
            return (now + timedelta(days=tage_unterschied)).strftime('%d.%m.%Y')
                
    return zeit_info

def get_days_left_string(termin_str):
    if not termin_str: return ""
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(termin_str))
    if match:
        try:
            task_date = datetime.strptime(match.group(0), '%d.%m.%Y').date()
            today = datetime.now().date()
            delta = (task_date - today).days
            if delta == 0: return "🚨 HEUTE!"
            elif delta == 1: return "⏳ Morgen!"
            elif delta < 0: return f"⚠️ Überfällig ({abs(delta)} Tage)"
            else: return f"⏳ Noch {delta} Tage"
        except ValueError: pass
    return ""

def is_within_next_fortnight(termin_str):
    if not termin_str: return False
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    max_date = now + timedelta(days=14)
    
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(termin_str))
    if match:
        try:
            task_date = datetime.strptime(match.group(0), '%d.%m.%Y')
            return now <= task_date <= max_date
        except ValueError: return False
        
    termin_lower = str(termin_str).lower()
    if any(k in termin_lower for k in ["diesen", "morgen", "übermorgen", "nächste woche"]):
        return True
    return False

# =========================================================================
# ADVANCED PERSISTENZ-SYSTEM (SUPABASE SYNC & SECURITY NET)
# =========================================================================
def load_from_supabase():
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{USER_ID}&select=app_state"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0].get('app_state')
        elif response.status_code != 200:
            st.sidebar.error(f"Supabase-Ladefehler: Status {response.status_code}")
    except Exception as e: st.sidebar.error(f"Datenbank-Ladefehler: {e}")
    return None

def save_to_supabase(state_data):
    if not state_data or "tasks" not in state_data: return
    
    # POSTGREST HEADERS FÜR EIN ECHTES UPSERT (ON CONFLICT)
    headers = {
        "apikey": SUPABASE_ANON_KEY, 
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}", 
        "Content-Type": "application/json", 
        "Prefer": "on-conflict=id, resolution=merge-duplicates"
    }
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data"
    payload = {"id": USER_ID, "app_state": state_data, "updated_at": datetime.utcnow().isoformat()}
    
    try: 
        res = requests.post(url, headers=headers, json=payload)
        # Sichert ab: Falls POST (409/400) wegen bestehender ID fehlschlägt -> Nutze PATCH-Fallback
        if res.status_code not in [200, 201]:
            patch_url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{USER_ID}"
            res_patch = requests.patch(patch_url, headers=headers, json={"app_state": state_data, "updated_at": datetime.utcnow().isoformat()})
            if res_patch.status_code not in [200, 204]:
                st.sidebar.error(f"🚨 Cloud-Sync fehlgeschlagen (POST: {res.status_code} / PATCH: {res_patch.status_code})")
            else:
                st.sidebar.success("☁️ Daten erfolgreich in Cloud gesichert!")
        else:
            st.sidebar.success("☁️ Daten erfolgreich in Cloud gesichert!")
    except Exception as e: 
        st.sidebar.error(f"🚨 Verbindungsfehler Cloud: {e}")

# =========================================================================
# AUDIO & KI EXTRAKTION (ID-BASED DELETION)
# =========================================================================
def transcribe_audio(audio_file):
    try:
        audio_data = audio_file.read()
        if not audio_data: return None
        transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_data, "audio/wav"))
        return transcript.text
    except Exception as e: 
        st.error(f"Audio-Fehler: {e}")
        return None

def extract_tasks_with_thinking(text, subjects_list, current_tasks):
    try:
        # Wir geben der KI Kontext über alle Aufgaben, die aktuell live existieren!
        tasks_context = [{"id": t.get("id"), "title": t.get("title"), "summary": t.get("summary"), "type": t.get("type"), "termin": t.get("termin")} for t in current_tasks]
        
        prompt = f"""Analysiere den folgenden Schul-Text extrem gründlich.
        Verfügbare Fächer: {', '.join(subjects_list)}
        
        Aktuelle Aufgaben auf dem Board:
        {json.dumps(tasks_context, ensure_ascii=False)}
        
        STRIKTE REGELN FÜR DIE SORTIERUNG:
        1. Wenn der User sagt, dass ein Termin NICHT stattfindet, abgesagt wurde, gelöscht werden soll oder erledigt ist:
           - Typ MUSS "delete" sein.
           - Suche in den 'Aktuellen Aufgaben auf dem Board' nach dem passenden Eintrag.
           - Trage die exakte "id" dieses Eintrags in das Feld "delete_id" ein.
        2. Wenn 'Test', 'Arbeit', 'Prüfung', 'Klausur', 'Schularbeit' vorkommt -> Typ MUSS "Test" sein.
        3. Wenn es ein 'Lernplan' ist -> Typ ist "Lernplan".
        4. Ansonsten -> Typ ist "Hausaufgabe".
        
        Antworte NUR mit einer JSON-Liste von Objekten:
        [
          {{
            "title": "Fachname", 
            "type": "Test" oder "Hausaufgabe" oder "Lernplan" oder "delete", 
            "summary": "Kurztitel", 
            "zeitpunkt": "z.B. 6.7.",
            "delete_id": "EXAKTE_ID_ZUM_LÖSCHEN_SONST_NULL"
          }}
        ]
        Text: "{text}" """
        
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.1)
        res_text = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        extracted_list = json.loads(res_text)
        
        tasks = []
        now_str = datetime.now().strftime("%d.%m.%Y")
        for item in extracted_list:
            raw_zeit = item.get("zeitpunkt", "Unbekannt") if item.get("zeitpunkt") else "Unbekannt"
            echtes_datum = parse_date_from_text(raw_zeit)
            
            tasks.append({
                "title": item.get("title", "Allgemein"),
                "type": item.get("type", "Hausaufgabe"),
                "summary": item.get("summary", "Neue Aufgabe"),
                "notes": text,
                "termin": echtes_datum, 
                "erstellt_am": now_str,
                "id": f"{datetime.utcnow().timestamp()}_{item.get('title')}",
                "delete_id": item.get("delete_id")
            })
        return tasks
    except Exception as e: 
        st.error(f"Fehler bei KI-Extraktion: {e}")
        return []

def process_user_input(input_text):
    if not input_text or input_text.strip().lower() in ["you", "you.", ""]: return

    new_tasks = extract_tasks_with_thinking(input_text, st.session_state.subjects, st.session_state.tasks)
    
    for task in new_tasks:
        if task["type"] == "delete":
            # Bulletproof ID-Löschung aus allen Spalten gleichzeitig!
            if task.get("delete_id"):
                st.session_state.tasks = [t for t in st.session_state.tasks if t.get("id") != task["delete_id"]]
            else:
                st.session_state.tasks = [t for t in st.session_state.tasks if not (t.get("title").lower() == task["title"].lower())]
        else:
            if not any(t.get("title") == task["title"] and t.get("summary") == task["summary"] for t in st.session_state.tasks):
                st.session_state.tasks.insert(0, task)
            
    st.session_state.messages.append({"role": "user", "content": input_text})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[{"role": "system", "content": "Bestätige kurz und knackig."}, {"role": "user", "content": input_text}], 
            temperature=0.2
        )
        st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
        save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
    except Exception as e: st.error(f"Fehler bei KI-Antwort: {e}")
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
        st.session_state.messages = [{"role": "assistant", "content": "Hi! 🐊 Dein Workspace ist live synchronisiert!"}]
        st.session_state.subjects = DEFAULT_SUBJECTS
    st.session_state.initialized = True

# =========================================================================
# SIDEBAR CONTROL CENTER
# =========================================================================
with st.sidebar:
    st.title("StudyTutor Pro 🐊")
    st.write("---")
    
    st.subheader("🔍 Workspace filtern")
    filter_subject = st.selectbox("Zeige nur Aufgaben für:", ["Alle Fächer"] + st.session_state.subjects)
    st.write("---")
    
    audio_file = st.audio_input("🎙️ Sprachbefehl aufnehmen")
    if audio_file and st.button("🚀 Sprachnachricht senden", use_container_width=True):
        text_from_speech = transcribe_audio(audio_file)
        if text_from_speech: process_user_input(text_from_speech)
    st.write("---")

    with st.expander("➕ Aufgabe schnell eintippen"):
        with st.form("manual_quick_form", clear_on_submit=True):
            m_sub = st.selectbox("Fach", st.session_state.subjects)
            m_type = m_type = st.selectbox("Typ", ["Hausaufgabe", "Test", "Lernplan"])
            m_sum = st.text_input("Was ist zu tun?")
            m_date = st.date_input("Bis wann?", datetime.now() + timedelta(days=1))
            if st.form_submit_button("Direkt eintragen"):
                st.session_state.tasks.insert(0, {
                    "title": m_sub, "type": m_type, "summary": m_sum, "notes": "Manuell eingetragen.",
                    "termin": m_date.strftime('%d.%m.%Y'), "erstellt_am": datetime.now().strftime("%d.%m.%Y"),
                    "id": f"manual_{datetime.utcnow().timestamp()}"
                })
                save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
                st.rerun()

    st.write("---")
    if st.button("🗑️ Alle Daten löschen", use_container_width=True):
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Zurückgesetzt."}]
        save_to_supabase({"tasks": [], "messages": st.session_state.messages, "subjects": st.session_state.subjects})
        st.rerun()

# =========================================================================
# MAIN CHAT EXPANDER
# =========================================================================
with st.expander("💬 KI-Lerncoach Chatverlauf", expanded=True):
    for msg in st.session_state.messages[-3:]:
        with st.chat_message(msg["role"]): st.write(msg["content"])
    if text_input := st.chat_input("Schreib deine Aufgaben hier hinein..."):
        process_user_input(text_input)

active_tasks = st.session_state.tasks if filter_subject == "Alle Fächer" else [t for t in st.session_state.tasks if t.get("title") == filter_subject]

# =========================================================================
# LIVE DASHBOARD DISPLAY WITH LIVE BUTTONS & COUNTDOWNS
# =========================================================================
st.write(f"### 📊 Mein Workspace ({filter_subject})")
col1, col2, col3 = st.columns(3)

# SPALTE 1: ARBEITEN
with col1:
    st.html("<div class='column-header'><span style='color: #ef4444;'>🔴</span> Tests & Arbeiten</div>")
    tests = [t for t in active_tasks if t.get("type") == "Test"]
    if not tests: st.caption("Keine Tests geplant. 🎉")
    for t in tests:
        countdown = get_days_left_string(t.get('termin', ''))
        cd_html = f"<div class='countdown-badge'>{countdown}</div>" if countdown else ""
        st.html(f"<div class='task-card' style='border-left-color: #ef4444;'><div class='card-info-line'>📅 {t.get('termin')}</div><div class='card-title'>{t['title']}</div><div class='card-summary'>{t['summary']}</div>{cd_html}</div>")
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            with st.popover("📝 Info", use_container_width=True): st.info(t["notes"])
        with btn_col2:
            if st.button("✅ Erledigt", key=f"del_{t['id']}", use_container_width=True):
                st.session_state.tasks = [task for task in st.session_state.tasks if task['id'] != t['id']]
                save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
                st.rerun()

# SPALTE 2: CHRONOLOGISCHE TIMELINE (NUR NÄCHSTE 14 TAGE)
with col2:
    st.html("<div class='column-header'><span style='color: #f59e0b;'>🟡</span> Diese & Nächste Woche</div>")
    upcoming = [t for t in active_tasks if t.get("type") in ["Hausaufgabe", "Test"] and is_within_next_fortnight(t.get("termin", ""))]
    
    if not upcoming: st.caption("Alles erledigt für die nächsten Wochen! 😎")
    for w in upcoming:
        is_test = w.get("type") == "Test"
        card_color = "#ef4444" if is_test else "#f59e0b"
        prefix = "⚠️ TEST | " if is_test else "📝 HÜ | "
        countdown = get_days_left_string(w.get('termin', ''))
        cd_html = f"<div class='countdown-badge'>{countdown}</div>" if countdown else ""
        
        st.html(f"<div class='task-card' style='border-left-color: {card_color};'><div class='card-info-line' style='color:#b45309; background:#fef3c7;'>📅 {w.get('termin')}</div><div class='card-title'>{prefix}{w['title']}</div><div class='card-summary'>{w['summary']}</div>{cd_html}</div>")
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            with st.popover("📝 Info", use_container_width=True): st.info(w["notes"])
        with btn_col2:
            if st.button("✅ Erledigt", key=f"del_up_{w['id']}", use_container_width=True):
                st.session_state.tasks = [task for task in st.session_state.tasks if task['id'] != w['id']]
                save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
                st.rerun()

# SPALTE 3: LERNPLAN
with col3:
    st.html("<div class='column-header'><span style='color: #10b981;'>🟢</span> Aktivierter Lernplan</div>")
    plan = [t for t in active_tasks if t.get("type") == "Lernplan"]
    if not plan: st.caption("Kein aktiver Lernplan.")
    for p in plan:
        st.html(f"<div class='task-card' style='border-left-color: #10b981;'><div class='card-title'>{p['title']}</div><div class='card-summary'>{p['summary']}</div></div>")
        if st.button("✅ Plan beenden", key=f"del_p_{p['id']}", use_container_width=True):
            st.session_state.tasks = [task for task in st.session_state.tasks if task['id'] != p['id']]
            save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
            st.rerun()
