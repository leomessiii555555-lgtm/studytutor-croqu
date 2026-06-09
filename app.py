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
    .countdown-badge { font-size: 0.8rem; font-weight: 600; color: #dc2626; margin-top: 4px; display: flex; align-items: center; gap: 4px; }
</style>
""")

# =========================================================================
# TIMELINE- & COUNTDOWN-LOGIK
# =========================================================================
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
    return False

# =========================================================================
# PERSISTENZ-SYSTEM (SABOTAGE-SICHERES SUPABASE SYNC)
# =========================================================================
def load_from_supabase():
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{USER_ID}&select=app_state"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            res_json = response.json()
            if res_json:
                return res_json[0].get('app_state')
        else:
            st.sidebar.error(f"❌ DB-Ladefehler: {response.status_code}")
    except Exception as e: 
        st.sidebar.error(f"🚨 Lade-Exception: {e}")
    return None

def save_to_supabase(state_data):
    if not state_data or "tasks" not in state_data: return
    headers = {
        "apikey": SUPABASE_ANON_KEY, 
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}", 
        "Content-Type": "application/json", 
        "Prefer": "on-conflict=id"
    }
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data"
    payload = {"id": USER_ID, "app_state": state_data, "updated_at": datetime.utcnow().isoformat()}
    try: 
        # 1. Versuch via POST (Upsert)
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code in [200, 201]:
            st.sidebar.success("☁️ Daten in Cloud gesichert!")
        else:
            # 2. Versuch via PATCH (Falls PostgREST den Upsert verweigert)
            patch_url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{USER_ID}"
            patch_res = requests.patch(patch_url, headers=headers, json={"app_state": state_data, "updated_at": datetime.utcnow().isoformat()})
            if patch_res.status_code in [200, 204]:
                st.sidebar.success("☁️ Daten in Cloud aktualisiert!")
            else:
                # ECHTE FEHLERMELDUNG ANZEIGEN
                st.sidebar.error(f"❌ DB-Fehler: POST {res.status_code} | PATCH {patch_res.status_code}")
                st.sidebar.caption(f"Details: {patch_res.text}")
    except Exception as e:
        st.sidebar.error(f"🚨 Sync-Exception: {e}")

# =========================================================================
# SINGLE-BRAIN REASONING ENGINE
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

def process_user_input(input_text):
    if not input_text or input_text.strip().lower() in ["you", "you.", ""]: return

    now = datetime.now()
    now_str = now.strftime("%d.%m.%Y")
    wochentage_map = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    weekday_str = wochentage_map[now.weekday()]

    tasks_context = [{"id": t.get("id"), "title": t.get("title"), "summary": t.get("summary"), "type": t.get("type"), "termin": t.get("termin")} for t in st.session_state.tasks]

    prompt = f"""Du bist der integrierte KI-Lerncoach für das Schüler-Board 'StudyTutor Pro'.
    Deine Aufgabe ist es, die User-Nachricht zu beantworten UND gleichzeitig im exakt selben Moment das Aufgabenboard im Hintergrund fehlerfrei zu steuern.

    HEUTIGES DATUM KONTEXT: {weekday_str}, der {now_str}
    Verfügbare Schulfächer: {', '.join(st.session_state.subjects)}

    Aktuelle Aufgaben auf dem Board:
    {json.dumps(tasks_context, ensure_ascii=False)}

    User-Nachricht: "{input_text}"

    STRIKTE REGELN FÜR REASONING UND DATUM:
    1. Berechne das Zieldatum im Format DD.MM.YYYY mathematisch präzise basierend auf heute ({now_str}, {weekday_str}).
    2. Wenn heute {weekday_str} ist und der User sagt "nächste Woche Mittwoch", meint er NICHT den morgigen bzw. diese Woche stattfindenden Mittwoch, sondern den Mittwoch der DARAUFFOLGENDEN Woche. Rechne das exakt aus!
    3. Wenn der User sagt, eine Aufgabe sei erledigt, findet nicht statt oder soll gelöscht werden, suche die passende ID aus der Liste der 'Aktuellen Aufgaben' heraus und setze sie in 'tasks_to_delete'.
    4. Schularbeiten, Tests, Klausuren, Prüfungen haben IMMER den Typ "Test".

    Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt. Verwende kein ```json oder sonstigen Text davor/danach.
    Format:
    {{
      "assistant_reply": "Deine direkte, motivierende Antwort an den Schüler (z.B. 'Ich habe deine Mathe-Schularbeit für nächsten Mittwoch, den 17.06., eingetragen! 🐊')",
      "tasks_to_add": [
        {{
          "title": "Fachname (MUSS exakt aus der Liste der verfügbaren Fächer sein)",
          "type": "Test" oder "Hausaufgabe" oder "Lernplan",
          "summary": "Prägnante Kurzbeschreibung (z.B. Mathe-Schularbeit)",
          "termin": "DD.MM.YYYY"
        }}
      ],
      "tasks_to_delete": ["Liste von IDs, die restlos gelöscht werden sollen"]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[{"role": "user", "content": prompt}], 
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content.strip())
        
        if result.get("tasks_to_delete"):
            st.session_state.tasks = [t for t in st.session_state.tasks if t.get("id") not in result["tasks_to_delete"]]
            
        if result.get("tasks_to_add"):
            for t in result["tasks_to_add"]:
                if not any(old.get("title") == t["title"] and old.get("summary") == t["summary"] and old.get("termin") == t["termin"] for old in st.session_state.tasks):
                    st.session_state.tasks.insert(0, {
                        "title": t.get("title"),
                        "type": t.get("type", "Hausaufgabe"),
                        "summary": t.get("summary"),
                        "notes": input_text,
                        "termin": t.get("termin"),
                        "erstellt_am": now_str,
                        "id": f"ai_{datetime.utcnow().timestamp()}_{t.get('title')}"
                    })
        
        st.session_state.messages.append({"role": "user", "content": input_text})
        st.session_state.messages.append({"role": "assistant", "content": result.get("assistant_reply", "Erledigt!")})
        
        save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects})
        
    except Exception as e: 
        st.error(f"Reasoning-Engine Fehler: {e}")
        
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
        st.session_state.messages = [{"role": "assistant", "content": "Hi! 🐊 Dein Pro-Board läuft. Lass uns testen, ob die Cloud hält!"}]
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
            m_type = st.selectbox("Typ", ["Hausaufgabe", "Test", "Lernplan"])
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
# LIVE DASHBOARD DISPLAY
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

# SPALTE 2: TIMELINE (NUR NÄCHSTE 14 TAGE)
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
