import streamlit as st
import openai
import requests
import json
import re
import base64
import time
from datetime import datetime, timedelta

# =========================================================================
# SICHERHEITS-KONFIGURATION & CLIENTS
# =========================================================================
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

client = openai.OpenAI(api_key=OPENAI_API_KEY)

DEFAULT_SUBJECTS = ["Mathe", "Deutsch", "Englisch", "Spanisch", "Geschichte", "Biologie", "Physik", "Chemie", "Geografie", "Informatik"]

st.set_page_config(page_title="StudyTutor Pro 🐊", layout="wide", initial_sidebar_state="expanded")

# PREMIUM CUSTOM CSS (AUTOMATISCHER DARK-MODE + VOLLES PLATTFORM-FEELING)
st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght=300;400;500;600;700&family=Orbitron:wght=500;700&display=swap');
    
    /* STANDARD HELLER MODUS */
    .stApp { background-color: #fafafa; color: #1e293b; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #f1f5f9; padding-top: 2rem; }
    
    /* EDEL-KALENDER DESIGN */
    .calendar-container { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 24px; }
    .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; margin-top: 15px; }
    .calendar-day-header { text-align: center; font-weight: 600; color: #64748b; font-size: 0.85rem; text-transform: uppercase; padding-bottom: 5px; }
    .calendar-cell { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; min-height: 95px; padding: 8px; display: flex; flex-direction: column; justify-content: space-between; }
    .calendar-cell.today { background: #eff6ff; border: 2px solid #3b82f6; }
    .calendar-date-num { font-weight: 700; font-size: 0.9rem; color: #475569; }
    .calendar-cell.today .calendar-date-num { color: #1d4ed8; }
    .calendar-dots { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; overflow-y: auto; max-height: 60px; }
    .calendar-dot { font-size: 0.7rem; font-weight: 600; padding: 2px 6px; border-radius: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: white; }
    
    /* GAMING LERNZENTRUM STYLES */
    .gaming-container { 
        background: linear-gradient(145deg, #0b0f19, #111827); 
        color: #f8fafc; padding: 35px; border-radius: 24px; 
        box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); border: 2px solid #4f46e5; margin-top: 10px;
    }
    .gaming-title { font-family: 'Orbitron', sans-serif; font-weight: 700; color: #6366f1; text-shadow: 0 0 10px rgba(99, 102, 241, 0.5); }
    .quest-card { background: rgba(31, 41, 55, 0.6); border: 1px solid #3b82f6; border-radius: 14px; padding: 18px; margin-bottom: 14px; border-left: 6px solid #3b82f6; }
    .quest-card.locked { border-color: #4b5563; border-left-color: #9ca3af; opacity: 0.4; background: rgba(17, 24, 39, 0.8); }
    .quest-card.active-quest { border-color: #a855f7; border-left-color: #a855f7; background: rgba(49, 46, 129, 0.4); box-shadow: 0 0 20px rgba(168, 85, 247, 0.25); }
    .kuckucksei-box { background: rgba(239, 68, 68, 0.1); border: 2px dashed #ef4444; border-radius: 14px; padding: 18px; margin-bottom: 16px; color: #fca5a5; }

    /* BOARDS & CARDS */
    .task-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 4px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border-left: 5px solid #ef4444; }
    .card-title { font-weight: 600; font-size: 1.1rem; color: #0f172a; margin-bottom: 4px; }
    .card-summary { font-size: 0.95rem; color: #1e293b; font-weight: 500; margin-bottom: 6px; }
    .card-info-line { font-size: 0.85rem; color: #e11d48; font-weight: 700; background: #ffe4e6; padding: 4px 8px; border-radius: 6px; display: inline-block; margin-bottom: 4px; }
    .column-header { font-size: 1.1rem; font-weight: 600; color: #334155; padding-bottom: 8px; margin-bottom: 16px; border-bottom: 2px solid #e2e8f0; }
    
    /* KARTEIKARTEN ENGINE STYLES */
    .flashcard-box { 
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: white; 
        border-radius: 20px; padding: 40px; text-align: center; min-height: 200px; 
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        box-shadow: 0 10px 25px rgba(29, 78, 216, 0.3); font-size: 1.4rem; font-weight: 600; margin-bottom: 20px;
    }
    .flashcard-box.flipped { background: linear-gradient(135deg, #10b981 0%, #047857 100%); box-shadow: 0 10px 25px rgba(4, 120, 87, 0.3); }

    .stat-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 16px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    .stat-val { font-size: 1.5rem; font-weight: 700; color: #0f172a; }
    .stat-lbl { font-size: 0.8rem; color: #64748b; font-weight: 500; }
    
    .grade-badge { background: #f1f5f9; padding: 6px 12px; border-radius: 8px; font-weight: 600; display: inline-block; margin: 4px; border: 1px solid #cbd5e1; color: #1e293b; }

    /* AUTOMATISCHER DUNKLER MODUS */
    @media (prefers-color-scheme: dark) {
        .stApp { background-color: #0f172a !important; color: #f8fafc !important; }
        [data-testid="stSidebar"] { background-color: #1e293b !important; border-right: 1px solid #334155 !important; }
        
        .calendar-container { background: #1e293b; border-color: #334155; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
        .calendar-cell { background: #0f172a; border-color: #334155; }
        .calendar-cell.today { background: #1e3a8a; border-color: #3b82f6; }
        .calendar-date-num { color: #94a3b8; }
        .calendar-cell.today .calendar-date-num { color: #60a5fa; }
        
        .task-card { background: #1e293b !important; border: 1px solid #334155 !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important; }
        .card-title { color: #f8fafc !important; }
        .card-summary { color: #cbd5e1 !important; }
        .card-info-line { background: #881337 !important; color: #fda4af !important; }
        .column-header { color: #94a3b8 !important; border-bottom: 2px solid #334155 !important; }
        
        .stat-card { background: #1e293b !important; border: 1px solid #334155 !important; box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important; }
        .stat-val { color: #f8fafc !important; }
        .stat-lbl { color: #94a3b8 !important; }
        
        .grade-badge { background: #1e293b !important; border: 1px solid #475569 !important; color: #f8fafc !important; }
        
        .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp span, .stApp label { color: #f8fafc !important; }
        .gaming-container p, .gaming-container h1, .gaming-container h2, .gaming-container h3, .gaming-container h4, .gaming-container h5, .gaming-container h6, .gaming-container span { color: #f8fafc !important; }
    }
</style>
""")

# =========================================================================
# BROWSER PUSH MITTEILUNGEN
# =========================================================================
st.html("""
<script>
    if (Notification.permission !== "granted" && Notification.permission !== "denied") {
        Notification.requestPermission();
    }
    window.sendKrokoNotification = function(title, body) {
        if (Notification.permission === "granted") {
            new Notification(title, { body: body, icon: "https://emojicdn.elk.sh/🐊" });
        }
    };
</script>
""")

def trigger_browser_notification(title, text):
    st.html(f"<script>window.sendKrokoNotification({json.dumps(title)}, {json.dumps(text)});</script>")

# =========================================================================
# GLOBAL PROFIL MANAGEMENT & KONTEN-ABRUF
# =========================================================================
def get_all_registered_profiles():
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data?select=id"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            profiles = [row["id"] for row in response.json() if row.get("id")]
            if "Alex" not in profiles: profiles.insert(0, "Alex")
            return sorted(list(set(profiles)))
    except Exception: pass
    return ["Alex"]

if "available_profiles" not in st.session_state:
    st.session_state.available_profiles = get_all_registered_profiles()
if "user_id" not in st.session_state:
    st.session_state.user_id = st.session_state.available_profiles[0]

# GLOBAL STATE INITIALISIERUNGEN
if "xp" not in st.session_state: st.session_state.xp = 0
if "streak" not in st.session_state: st.session_state.streak = 0
if "flashcards" not in st.session_state: st.session_state.flashcards = []
if "card_flipped" not in st.session_state: st.session_state.card_flipped = False
if "card_idx" not in st.session_state: st.session_state.card_idx = 0
if "notified_task_ids" not in st.session_state: st.session_state.notified_task_ids = []
if "gaming_quests" not in st.session_state: st.session_state.gaming_quests = []
if "kuckuckseier" not in st.session_state: st.session_state.kuckuckseier = []
if "handwriting_analysis" not in st.session_state: st.session_state.handwriting_analysis = ""
if "active_summary" not in st.session_state: st.session_state.active_summary = ""

# =========================================================================
# UTILITIES
# =========================================================================
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.read()).decode('utf-8')

def transcribe_audio(audio_file):
    try:
        audio_data = audio_file.read()
        if not audio_data: return None
        transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_data, "audio/wav"))
        return transcript.text
    except Exception: return None

def get_days_left(termin_str):
    if not termin_str: return None
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', str(termin_str))
    if match:
        try:
            task_date = datetime.strptime(match.group(0), '%d.%m.%Y').date()
            today = datetime.now().date()
            return (task_date - today).days
        except ValueError: pass
    return None

def check_and_send_deadline_notifications():
    if "tasks" not in st.session_state or not st.session_state.tasks: return
    for t in st.session_state.tasks:
        t_id = t.get("id")
        if t_id and t_id not in st.session_state.notified_task_ids:
            days_left = get_days_left(t.get("termin"))
            if days_left is not None and 0 <= days_left <= 2:
                fach = t.get("title", "Aufgabe")
                thema = t.get("summary", "")
                typ = t.get("type", "Aufgabe")
                zeit_text = "ist HEUTE fällig!" if days_left == 0 else ("ist morgen fällig!" if days_left == 1 else f"ist in nur noch {days_left} Tagen!")
                trigger_browser_notification("🐊 StudyTutor Pro Mitteilung", f"{st.session_state.user_id}, dein(e) {typ} in {fach} ({thema}) {zeit_text} ⏳")
                st.session_state.notified_task_ids.append(t_id)

# =========================================================================
# PERSISTENZ-SYSTEM (SUPABASE)
# =========================================================================
def load_from_supabase():
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{st.session_state.user_id}&select=app_state"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            res_json = response.json()
            if res_json: return res_json[0].get('app_state')
    except Exception: pass
    return None

def save_to_supabase(state_data):
    if not state_data or "tasks" not in state_data: return
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}", "Content-Type": "application/json", "Prefer": "on-conflict=id"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data"
    payload = {"id": st.session_state.user_id, "app_state": state_data, "updated_at": datetime.utcnow().isoformat()}
    try: 
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code not in [200, 201]:
            patch_url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{st.session_state.user_id}"
            requests.patch(patch_url, headers=headers, json={"app_state": state_data, "updated_at": datetime.utcnow().isoformat()})
    except Exception: pass

def save_all_to_db():
    save_to_supabase({
        "tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects,
        "completed_count": st.session_state.get("completed_count", 0), "grades": st.session_state.grades, "xp": st.session_state.xp,
        "streak": st.session_state.streak, "flashcards": st.session_state.flashcards, "gaming_quests": st.session_state.gaming_quests,
        "kuckuckseier": st.session_state.kuckuckseier, "handwriting_analysis": st.session_state.handwriting_analysis
    })

def process_user_input(input_text, uploaded_image=None):
    if (not input_text or input_text.strip() == "") and not uploaded_image: return
    with st.spinner("Überlege... 🐊"):
        now = datetime.now()
        now_str = now.strftime("%d.%m.%Y")
        wochentage = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        heute_wochentag = wochentage[now.weekday()]

        # HOCHPRÄZISE DATUMS-ANWEISUNG UM FEHLBERECHNUNGEN ZU VERHINDERN
        prompt = f"""Du bist der integrierte KI-Lerncoach für das Schüler-Board 'StudyTutor Pro'.
        HEUTE IST: {heute_wochentag}, der {now_str}.
        
        STRIKTE MATHEMATISCHE DATUMS-BERECHNUNG:
        Wenn der User relative Zeitangaben macht, berechne das exakte Datum ausgehend von heute ({now_str}):
        - "diesen Freitag" = Freitag derselben Woche.
        - "nächsten Freitag" / "nächste Woche Freitag" = Freitag der NÄCHSTEN Kalenderwoche. 
          Beispiel: Wenn heute Dienstag der 09.06.2026 ist, ist "diesen Freitag" der 12.06.2026 und "nächste Woche Freitag" ist EXAKT der 19.06.2026.
        Rechne mathematisch und kalendarisch fehlerfrei!
        Falls der User ein Fach abkürzt (z.B. "bgeo"), ordne es dem passenden Fach zu (z.B. "Geografie").

        Verfügbare Schulfächer: {', '.join(st.session_state.subjects)}
        Aktuelle Aufgaben auf dem Board: {json.dumps(st.session_state.tasks, ensure_ascii=False)}

        User-Nachricht: "{input_text}"

        Antworte AUSSCHLIESSLICH im validen JSON-Format:
        {{
          "assistant_reply": "Deine persönliche, motivierende Antwort an den Schüler.",
          "tasks_to_add": [
            {{ "title": "Fachname", "type": "Test" oder "Hausaufgabe", "summary": "Thema", "prioritaet": "🚨 Hoch" oder "🟡 Mittel", "termin": "DD.MM.YYYY" }}
          ],
          "tasks_to_delete": [],
          "grade_to_add": null,
          "flashcards_to_add": []
        }}"""
        content_payload = [{"type": "text", "text": prompt}]
        if uploaded_image:
            content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image(uploaded_image)}"} })
        try:
            response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": content_payload}], response_format={"type": "json_object"}, temperature=0.1)
            result = json.loads(response.choices[0].message.content.strip())
            
            if result.get("tasks_to_add"):
                for i, t in enumerate(result["tasks_to_add"]):
                    st.session_state.tasks.insert(0, {
                        "title": t.get("title"), "type": t.get("type", "Hausaufgabe"), "summary": t.get("summary"), "prioritaet": t.get("prioritaet", "🟡 Mittel"),
                        "termin": t.get("termin"), "id": f"ai_{datetime.utcnow().timestamp()}_{i}"
                    })
                    
            st.session_state.messages.append({"role": "user", "content": input_text if input_text else "📸 [Bild hochgeladen]"})
            st.session_state.messages.append({"role": "assistant", "content": result.get("assistant_reply", "Erledigt! 🐊")})
            
            save_all_to_db()
        except Exception as e: st.error(f"Fehler: {e}")
    st.rerun()

# =========================================================================
# RE-INITIALISIERUNG BEI NUTZERWECHSEL
# =========================================================================
if "initialized_user" not in st.session_state or st.session_state.initialized_user != st.session_state.user_id:
    db_state = load_from_supabase()
    if db_state:
        st.session_state.tasks = db_state.get("tasks", [])
        st.session_state.messages = db_state.get("messages", [])
        st.session_state.subjects = db_state.get("subjects", DEFAULT_SUBJECTS)
        st.session_state.completed_count = db_state.get("completed_count", 0)
        st.session_state.grades = db_state.get("grades", [])
        st.session_state.xp = db_state.get("xp", 0)
        st.session_state.streak = db_state.get("streak", 0)
        st.session_state.flashcards = db_state.get("flashcards", [])
        st.session_state.gaming_quests = db_state.get("gaming_quests", [])
        st.session_state.kuckuckseier = db_state.get("kuckuckseier", [])
        st.session_state.handwriting_analysis = db_state.get("handwriting_analysis", "")
    else:
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": f"Hi {st.session_state.user_id}! 🐊 Ich habe den Chat für uns zurückgesetzt. Alles ist frisch. Wie kann ich dir heute helfen?"}]
        st.session_state.subjects = DEFAULT_SUBJECTS
        st.session_state.completed_count = 0
        st.session_state.grades = []
        st.session_state.xp = 0
        st.session_state.streak = 0
        st.session_state.flashcards = []
        st.session_state.gaming_quests = []
        st.session_state.kuckuckseier = []
        st.session_state.handwriting_analysis = ""
    st.session_state.initialized_user = st.session_state.user_id

check_and_send_deadline_notifications()

# =========================================================================
# NAVIGATION CONTROL PANEL (SIDEBAR)
# =========================================================================
with st.sidebar:
    st.title("StudyTutor Pro 🐊")
    st.write("---")
    
    if "app_mode" not in st.session_state: st.session_state.app_mode = "Dashboard"
    
    st.subheader("🕹️ Navigation Portal")
    if st.button("📊 Dashboard & Board", use_container_width=True, type="primary" if st.session_state.app_mode == "Dashboard" else "secondary"):
        st.session_state.app_mode = "Dashboard"; st.rerun()
    if st.button("🃏 Karteikarten-Trainer", use_container_width=True, type="primary" if st.session_state.app_mode == "Karteikarten" else "secondary"):
        st.session_state.app_mode = "Karteikarten"; st.rerun()
    if st.button("📝 Notenspiegel", use_container_width=True, type="primary" if st.session_state.app_mode == "Notenspiegel" else "secondary"):
        st.session_state.app_mode = "Notenspiegel"; st.rerun()
    if st.button("🎯 Kroko-Lernzentrum", use_container_width=True, type="primary" if st.session_state.app_mode == "Lernzentrum" else "secondary"):
        st.session_state.app_mode = "Lernzentrum"; st.rerun()
        
    st.write("---")
    st.subheader("🐊 Deine Kroko-Stats")
    level = (st.session_state.xp // 100) + 1
    st.write(f"**Level {level}** ({(st.session_state.xp % 100)}/100 XP)")
    st.progress((st.session_state.xp % 100) / 100)
    st.write(f"🔥 **Lern-Streak:** {st.session_state.streak} Tage")
    
    st.write("---")
    st.subheader("👥 Profil-Verwaltung")
    if st.session_state.user_id not in st.session_state.available_profiles:
        st.session_state.available_profiles.append(st.session_state.user_id)
    st.session_state.available_profiles = sorted(list(set(st.session_state.available_profiles)))
    
    current_profile_idx = st.session_state.available_profiles.index(st.session_state.user_id)
    selected_user = st.selectbox("Profil wechseln:", options=st.session_state.available_profiles, index=current_profile_idx)
    if selected_user != st.session_state.user_id:
        st.session_state.user_id = selected_user; st.rerun()
        
    with st.expander("➕ / 🗑️ Profile verwalten"):
        new_prof_name = st.text_input("Neues Profil erstellen:", placeholder="Name eingeben...")
        if st.button("Profil anlegen 🚀", use_container_width=True):
            if new_prof_name and new_prof_name.strip() not in st.session_state.available_profiles:
                cleaned_name = new_prof_name.strip()
                st.session_state.available_profiles.append(cleaned_name)
                st.session_state.user_id = cleaned_name
                save_all_to_db()
                st.success(f"Profil '{cleaned_name}' gestartet!")
                st.rerun()

# =========================================================================
# MODUS 1: DASHBOARD & WORKSPACE BOARD
# =========================================================================
if st.session_state.app_mode == "Dashboard":
    st.title("Dein Alltags-Cockpit 📊")
    
    st.markdown("### 📅 Dein smarter Terminkalender")
    with st.container(border=False):
        st.html("<div class='calendar-container'>")
        cols = st.columns(7)
        days_letters = ["MO", "DI", "MI", "DO", "FR", "SA", "SO"]
        for i, d in enumerate(days_letters): cols[i].html(f"<div class='calendar-day-header'>{d}</div>")
            
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        
        grid_cols = st.columns(7)
        for i in range(7):
            current_day = start_of_week + timedelta(days=i)
            day_str = current_day.strftime("%d.%m.%Y")
            is_today = "today" if current_day == today else ""
            
            dots_html = ""
            for t in st.session_state.tasks:
                if t.get("termin") == day_str:
                    color = "#ef4444" if t.get("type") == "Test" else "#f59e0b"
                    dots_html += f"<div class='calendar-dot' style='background:{color};'>{t['title']}: {t['summary']}</div>"
                    
            grid_cols[i].html(f"""
            <div class='calendar-cell {is_today}'>
                <div class='calendar-date-num'>{current_day.day}</div>
                <div class='calendar-dots'>{dots_html}</div>
            </div>
            """)
        st.html("</div>")

    with st.expander(f"💬 KI-Lerncoach & Mentor (Sprach- & Bild-Support)", expanded=True):
        for msg in st.session_state.messages[-4:]:
            with st.chat_message(msg["role"]): st.write(msg["content"])
            
        c_btn1, c_btn2 = st.columns([6, 1])
        with c_btn2:
            if st.button("🗑️ Reset", help="Löscht den aktuellen Chatverlauf"):
                st.session_state.messages = [{"role": "assistant", "content": f"Hi {st.session_state.user_id}! Ich habe unseren Chat zurückgesetzt. Lass uns neu durchstarten! 🐊"}]
                save_all_to_db()
                st.rerun()
                
        with st.form("quick_chat_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns([4, 3, 1], vertical_alignment="center")
            with f_col1: c_text = st.text_input("Frag Kroko oder diktiere...", key="chat_in", label_visibility="collapsed")
            with f_col2: c_audio = st.audio_input("Diktieren", key="chat_aud", label_visibility="collapsed")
            with f_col3: submit = st.form_submit_button("🚀", use_container_width=True)
            if submit:
                final_text = c_text.strip() if c_text else ""
                if c_audio:
                    a_txt = transcribe_audio(c_audio)
                    if a_txt: final_text = f"{final_text} {a_txt}".strip()
                if final_text: process_user_input(final_text)

    st.write("### 🗂️ Dein Workspace-Board")
    col1, col2 = st.columns(2)
    with col1:
        st.html("<div class='column-header'><span style='color: #ef4444;'>🔴</span> Tests & Arbeiten</div>")
        for t in [t for t in st.session_state.tasks if t.get("type") == "Test"]:
            st.html(f"<div class='task-card'><div class='card-info-line'>📅 {t['termin']}</div><div class='card-title'>{t['title']}</div><div class='card-summary'>{t['summary']}</div></div>")
            if st.button("Erledigt ✅", key=f"del_{t['id']}", use_container_width=True):
                st.session_state.tasks = [task for task in st.session_state.tasks if task['id'] != t['id']]
                st.session_state.xp += 20; save_all_to_db(); st.rerun()
    with col2:
        st.html("<div class='column-header'><span style='color: #f59e0b;'>🟡</span> Hausaufgaben</div>")
        for t in [t for t in st.session_state.tasks if t.get("type") == "Hausaufgabe"]:
            st.html(f"<div class='task-card' style='border-left-color:#f59e0b;'><div class='card-info-line' style='background:#fef3c7; color:#b45309;'>📅 {t['termin']}</div><div class='card-title'>{t['title']}</div><div class='card-summary'>{t['summary']}</div></div>")
            if st.button("Erledigt ✅", key=f"del_{t['id']}", use_container_width=True):
                st.session_state.tasks = [task for task in st.session_state.tasks if task['id'] != t['id']]
                st.session_state.xp += 10; save_all_to_db(); st.rerun()

# =========================================================================
# MODUS 2: KARTEIKARTEN-TRAINER
# =========================================================================
elif st.session_state.app_mode == "Karteikarten":
    st.title("🃏 Intelligenter Karteikarten-Trainer")
    st.markdown("Lerne aktiv mit deinen erstellten Stapeln oder lass dir blitzschnell neue KI-Karten schmieden.")
    
    if st.session_state.flashcards:
        idx = st.session_state.card_idx % len(st.session_state.flashcards)
        card = st.session_state.flashcards[idx]
        
        fach = card.get('subject', 'Allgemein')
        frage = card.get('question', 'Keine Frage hinterlegt')
        antwort = card.get('answer', 'Keine Antwort hinterlegt')
        
        if st.session_state.card_flipped:
            st.html(f"<div class='flashcard-box flipped'>💡 Antwort:<br>{antwort}</div>")
        else:
            st.html(f"<div class='flashcard-box'>❓ Frage ({fach}):<br>{frage}</div>")
            
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            if st.button("🔄 Karte umdrehen", use_container_width=True):
                st.session_state.card_flipped = not st.session_state.card_flipped; st.rerun()
        with b_col2:
            if st.button("✅ Gewusst (+5 XP)", use_container_width=True):
                st.session_state.xp += 5; st.session_state.card_idx += 1
                st.session_state.card_flipped = False; save_all_to_db(); st.success("Stark! Weiter so."); time.sleep(0.5); st.rerun()
        with b_col3:
            if st.button("❌ Nicht gewusst", use_container_width=True):
                st.session_state.card_idx += 1; st.session_state.card_flipped = False; st.rerun()
                
        if st.button("🗑️ Diese Karte löschen", use_container_width=True):
            st.session_state.flashcards.pop(idx)
            save_all_to_db(); st.rerun()
    else:
        st.info("Dein Karteikastendeck ist aktuell leer. Generiere neue Karten über das Formular unten!")

    st.write("---")
    
    with st.expander("🤖 Blitzschnelle KI-Karten schmieden (mit Sprachsteuerung)", expanded=False):
        with st.form("ki_card_generation_form"):
            ki_sub = st.selectbox("Fach:", st.session_state.subjects, key="ki_card_sub")
            ki_text_wish = st.text_input("Thema / Stoffgebiet:", placeholder="z.B. Vokabeln Unidad 2, Deklinationen...")
            ki_aud_wish = st.audio_input("Thema per Sprache einsprechen:")
            ki_diff = st.select_slider("Schwierigkeitsgrad:", options=["Sehr Einfach", "Mittel", "Schwer / Knifflig"], value="Mittel")
            ki_count = st.number_input("Anzahl der Karten:", min_value=1, max_value=12, value=5)
            
            if st.form_submit_button("🔥 KI-Karten erschaffen"):
                final_topic = ki_text_wish.strip() if ki_text_wish else ""
                if ki_aud_wish:
                    trans = transcribe_audio(ki_aud_wish)
                    if trans: final_topic = f"{final_topic} {trans}".strip()
                
                if final_topic:
                    with st.spinner("Kroko designt deine Premium-Karten... 🐊"):
                        ki_prompt = f"""Erstelle exakt {ki_count} Karteikarten für das Schulfach '{ki_sub}' zum Thema '{final_topic}'.
                        Schwierigkeit: {ki_diff}.
                        Antworte AUSSCHLIESSLICH im folgendem validen JSON-Format:
                        {{
                          "flashcards": [
                            {{ "subject": "{ki_sub}", "question": "Fragetext", "answer": "Antworttext" }}
                          ]
                        }}"""
                        try:
                            res = client.chat.completions.create(
                                model="gpt-4o-mini", messages=[{"role": "user", "content": ki_prompt}],
                                response_format={"type": "json_object"}, temperature=0.6
                            )
                            generated_cards = json.loads(res.choices[0].message.content.strip()).get("flashcards", [])
                            for c in generated_cards:
                                st.session_state.flashcards.append({
                                    "subject": c.get("subject", ki_sub), "question": c.get("question", ""), "answer": c.get("answer", "")
                                })
                            save_all_to_db()
                            st.success(f"🎉 {len(generated_cards)} Karten wurden in den Stapel gepackt!")
                            time.sleep(1); st.rerun()
                        except Exception as e: st.error(f"Fehler beim Generieren: {e}")
                else:
                    st.warning("Bitte gib ein Thema ein oder nutze die Sprachnachricht!")

    with st.expander("➕ Klassisch manuelle Lernkarte hinzufügen", expanded=False):
        with st.form("add_card_form"):
            f_sub = st.selectbox("Fach:", st.session_state.subjects)
            f_q = st.text_input("Frage:")
            f_a = st.text_input("Antwort:")
            if st.form_submit_button("Karte einpacken"):
                if f_q and f_a:
                    st.session_state.flashcards.append({"subject": f_sub, "question": f_q, "answer": f_a})
                    save_all_to_db(); st.success("Karte hinzugefügt!"); st.rerun()

# =========================================================================
# MODUS 3: NOTENSPIEGEL
# =========================================================================
elif st.session_state.app_mode == "Notenspiegel":
    st.title("📝 Dein persönlicher Notenspiegel (Österreichische Gewichtung)")
    st.markdown("Verwalte deine Noten nach dem österreichischen AHS/BMHS-System: Schularbeiten zählen **50%**, Tests **25%** und die Mitarbeit **25%** der Gesamtnote.")
    
    with st.form("grade_form"):
        g_col1, g_col2, g_col3 = st.columns(3)
        with g_col1: g_sub = st.selectbox("Fach:", st.session_state.subjects)
        with g_col2: g_val = st.number_input("Note (1-5):", min_value=1.0, max_value=5.0, step=1.0)
        with g_col3: g_type = st.selectbox("Leistungsart:", ["Schularbeit (SA)", "Test", "Mitarbeit"])
        g_lbl = st.text_input("Beschreibung (z.B. Vocabulario Test, Referat):")
        if st.form_submit_button("Note eintragen 📝"):
            st.session_state.grades.append({
                "subject": g_sub, "grade": g_val, "label": g_type, "desc": g_lbl, "date": datetime.now().strftime("%d.%m.%Y")
            })
            save_all_to_db(); st.success("Eingetragen!"); st.rerun()

    if st.session_state.grades:
        st.write("### 📈 Deine Fachübersichten & präzise Schnitte")
        for s in st.session_state.subjects:
            sub_grades = [g for g in st.session_state.grades if g["subject"] == s]
            if sub_grades:
                sa_list = [g["grade"] for g in sub_grades if g.get("label") == "Schularbeit (SA)"]
                test_list = [g["grade"] for g in sub_grades if g.get("label") == "Test"]
                mit_list = [g["grade"] for g in sub_grades if g.get("label") == "Mitarbeit"]
                
                has_sa, has_test, has_mit = len(sa_list) > 0, len(test_list) > 0, len(mit_list) > 0
                
                if has_sa and has_test and has_mit:
                    avg = ( (sum(sa_list)/len(sa_list)) * 0.50 ) + ( (sum(test_list)/len(test_list)) * 0.25 ) + ( (sum(mit_list)/len(mit_list)) * 0.25 )
                    details = f"(SA: 50% | Test: 25% | Mitarbeit: 25%)"
                elif has_sa and has_test:
                    avg = ( (sum(sa_list)/len(sa_list)) * 0.65 ) + ( (sum(test_list)/len(test_list)) * 0.35 )
                    details = f"(Gewichtet: SA 65% / Test 35%)"
                elif has_sa and has_mit:
                    avg = ( (sum(sa_list)/len(sa_list)) * 0.60 ) + ( (sum(mit_list)/len(mit_list)) * 0.40 )
                    details = f"(Gewichtet: SA 60% / Mitarbeit 40%)"
                elif has_test and has_mit:
                    avg = ( (sum(test_list)/len(test_list)) * 0.50 ) + ( (sum(mit_list)/len(mit_list)) * 0.50 )
                    details = f"(Gewichtet: Test 50% / Mitarbeit 50% — Keine SA)"
                elif has_sa:
                    avg = sum(sa_list) / len(sa_list)
                    details = "(Bisher nur Schularbeitsnote)"
                elif has_test:
                    avg = sum(test_list) / len(test_list)
                    details = "(Bisher nur Testnote)"
                else:
                    avg = sum(mit_list) / len(mit_list)
                    details = "(Bisher nur Mitarbeit)"
                
                st.markdown(f"#### **{s}** — Errechneter Stand: **{avg:.2f}**")
                st.caption(f"ℹ️ *{details}*")
                
                for idx, g in enumerate(st.session_state.grades):
                    if g["subject"] == s:
                        g_col, del_col = st.columns([5, 1])
                        with g_col:
                            st.html(f"<span class='grade-badge'>{int(g['grade'])}</span> <b>{g.get('label','')}</b>: {g.get('desc','')} ({g['date']})")
                        with del_col:
                            if st.button("🗑️", key=f"del_g_{idx}"):
                                st.session_state.grades.pop(idx)
                                save_all_to_db(); st.rerun()
                st.write("---")
    else:
        st.info("Noch keine Noten eingetragen.")

# =========================================================================
# MODUS 4: KROKO-LERNZENTRUM
# =========================================================================
elif st.session_state.app_mode == "Lernzentrum":
    st.html("<div class='gaming-container'>")
    st.html("<h1 class='gaming-title'>🎯 Kroko-Lernzentrum (Fokus-Modus)</h1>")
    
    st.write("---")
    st.subheader("📚 KI-Stoff-Zusammenfasser (mit Sprachnachrichten-Support)")
    with st.expander("Lade Skripte hoch oder sprich deinen Lernstoff einfach ein!", expanded=True):
        sum_text = st.text_area("Lernstoff reinkopieren:", placeholder="Füge hier dicken Text ein...", height=150)
        sum_audio = st.audio_input("Oder diktiere deinen Stoff live per Sprachnachricht:")
        sum_file = st.file_uploader("Optional: Textdatei (.txt) hochladen:", type=["txt"])
        
        if st.button("Stoff knackig zusammenfassen! ✨", use_container_width=True):
            final_source = sum_text.strip() if sum_text else ""
            if sum_file:
                final_source += "\n" + sum_file.read().decode("utf-8")
            if sum_audio:
                with st.spinner("Transkribiere Sprachnachricht... 🎙️"):
                    trans = transcribe_audio(sum_audio)
                    if trans: final_source += "\n" + trans
                    
            if final_source.strip():
                with st.spinner("Kroko destilliert die Kernpunkte heraus... 🐊"):
                    try:
                        res = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": f"Fasse folgenden Stoff hochstrukturiert zusammen. Nutze Bulletpoints, hebe Kernbegriffe fett hervor und mache es perfekt zum Lernen:\n\n{final_source}"}]
                        )
                        st.session_state.active_summary = res.choices[0].message.content.strip()
                    except Exception as e: st.error(f"Fehler: {e}")
            else:
                st.warning("Bitte gib Text ein, uploade ein File oder sprich eine Nachricht ein!")
                
        if st.session_state.active_summary:
            st.markdown("#### 📝 Deine fertige Zusammenfassung:")
            st.info(st.session_state.active_summary)

    st.write("---")
    st.subheader("✍️ Musterschrift-Gedächtnis (Schrift lernen)")
    with st.expander("Bringe Kroko deine persönliche Handschrift bei", expanded=False):
        st.info("📝 **Schreibe bitte folgenden Satz auf ein Blatt Papier und lade das Foto hoch:**\n\n*„Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. Kroko lernt 12345!“*")
        sample_img = st.file_uploader("Foto deiner Handschriftprobe hochladen:", type=["jpg", "jpeg", "png"])
        if st.button("Schriftprobe analysieren!") and sample_img:
            with st.spinner("Analysiere..."):
                img_b64 = encode_image(sample_img)
                try:
                    res = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": [
                            {"type": "text", "text": "Analysiere die Handschrift."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]}]
                    )
                    st.session_state.handwriting_analysis = res.choices[0].message.content.strip()
                    save_all_to_db(); st.success("Erfolgreich gelernt!"); st.rerun()
                except Exception as e: st.error(f"Fehler: {e}")
        if st.session_state.handwriting_analysis:
            st.caption(f"**Schriftprofil:** {st.session_state.handwriting_analysis}")

    st.write("---")
    st.subheader("🥚 Deine aktiven Kuckuckseier")
    
    if st.session_state.kuckuckseier:
        for idx, egg in enumerate(st.session_state.kuckuckseier):
            st.html(f"<div class='kuckucksei-box'><h4>⚠️ Kuckucksei #{idx+1}</h4><p><b>Fach:</b> {egg['subject']} | <b>Fehler:</b> {egg['error_found']}</p><p><b>⚔️ Challenge:</b> {egg['training_task']}</p></div>")
            with st.form(f"solve_egg_form_{idx}"):
                ans_text = st.text_area("Deine Antwort (Text):", key=f"egg_ans_txt_{idx}")
                ans_audio = st.audio_input("Oder sprich deine Lösung ein:", key=f"egg_ans_aud_{idx}")
                
                if st.form_submit_button("Lösung einreichen!"):
                    final_ans = ans_text.strip() if ans_text else ""
                    if ans_audio:
                        trans = transcribe_audio(ans_audio)
                        if trans: final_ans = f"{final_ans} {trans}".strip()
                        
                    if final_ans:
                        with st.spinner("Prüfe..."):
                            try:
                                chk = client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    messages=[{"role": "user", "content": f"Aufgabe: {egg['training_task']}\nAntwort: {final_ans}\nKorrekt? JSON: {{'correct': true/false, 'feedback': '...'}}"}],
                                    response_format={"type": "json_object"}
                                )
                                eval_res = json.loads(chk.choices[0].message.content.strip())
                                if eval_res.get("correct") == True:
                                    st.success("🎉 Gefixt! +30 XP")
                                    st.session_state.xp += 30; st.session_state.kuckuckseier.pop(idx)
                                    save_all_to_db(); time.sleep(1); st.rerun()
                                else: st.error(f"❌ {eval_res.get('feedback')}")
                            except Exception: pass
                    else:
                        st.warning("Bitte gib eine Antwort ein oder sprich sie ein!")
    else: st.info("Alles fehlerfrei!")

    with st.expander("📸 Korrigierte Arbeiten einsenden"):
        uploaded_corrs = st.file_uploader("Bilder hochladen:", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        corr_sub = st.selectbox("Für welches Fach?", st.session_state.subjects, key="corr_sub_box")
        if st.button("Scans starten 👁️") and uploaded_corrs:
            with st.spinner("Kroko scannt..."):
                for f in uploaded_corrs[:4]:
                    img_b64 = encode_image(f)
                    scan_prompt = f"Finde Fehler für {corr_sub}. Antworte als JSON: {{ 'error_found': '...', 'training_task': '...' }}"
                    try:
                        res = client.chat.completions.create(
                            model="gpt-4o-mini", messages=[{"role": "user", "content": [{"type": "text", "text": scan_prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
                            response_format={"type": "json_object"}
                        )
                        scan_res = json.loads(res.choices[0].message.content.strip())
                        st.session_state.kuckuckseier.append({"subject": corr_sub, "error_found": scan_res.get("error_found"), "training_task": scan_res.get("training_task")})
                    except Exception: pass
                save_all_to_db(); st.rerun()

    st.write("---")
    st.subheader("🗺️ Deine active Quest-Reihe")
    quests_blocked = len(st.session_state.kuckuckseier) > 0
    
    if not st.session_state.gaming_quests:
        with st.form("quest_gen_form"):
            q_sub = st.selectbox("Für welches Fach?", st.session_state.subjects)
            q_top = st.text_input("Thema:")
            if st.form_submit_button("🔥 Quest-Reihe schmieden!"):
                if q_top:
                    with st.spinner("Schmiede..."):
                        try:
                            res = client.chat.completions.create(
                                model="gpt-4o-mini", messages=[{"role": "user", "content": f"Baue 3 Quests für {q_sub} Thema {q_top}. JSON: {{ 'quests': [ {{ 'step': 1, 'title': '...', 'description': '...' }} ] }}"}],
                                response_format={"type": "json_object"}
                            )
                            st.session_state.gaming_quests = json.loads(res.choices[0].message.content.strip()).get("quests", [])
                            save_all_to_db(); st.rerun()
                        except Exception: pass
    else:
        for idx, q in enumerate(st.session_state.gaming_quests):
            is_locked = "locked" if quests_blocked else ("active-quest" if idx == 0 else "")
            st.html(f"<div class='quest-card {is_locked}'><h4>Quest {q.get('step')}: {q.get('title')}</h4><p>{q.get('description')}</p></div>")
            if idx == 0 and not quests_blocked:
                if st.button("Quest abschließen! 🏆"):
                    st.session_state.gaming_quests.pop(0)
                    st.session_state.xp += 25; save_all_to_db(); st.balloons(); st.rerun()
