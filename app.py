import streamlit as st
import openai
import requests
import json
import re
import base64
from datetime import datetime, timedelta

# =========================================================================
# SICHERHEITS-KONFIGURATION & CLIENTS
# =========================================================================
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

client = openai.OpenAI(api_key=OPENAI_API_KEY)

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
    
    .focus-box {
        background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%);
        color: #ffffff;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-left: 6px solid #a855f7;
    }
    
    .stat-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px 16px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .stat-val { font-size: 1.5rem; font-weight: 700; color: #0f172a; }
    .stat-lbl { font-size: 0.8rem; color: #64748b; font-weight: 500; }
    
    .grade-badge {
        background: #f1f5f9;
        padding: 6px 12px;
        border-radius: 8px;
        font-weight: 600;
        display: inline-block;
        margin: 4px;
        border: 1px solid #cbd5e1;
    }
</style>
""")

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
            if "Alex" not in profiles:
                profiles.insert(0, "Alex")
            return sorted(list(set(profiles)))
    except Exception: pass
    return ["Alex"]

if "available_profiles" not in st.session_state:
    st.session_state.available_profiles = get_all_registered_profiles()

if "user_id" not in st.session_state:
    st.session_state.user_id = st.session_state.available_profiles[0]

# =========================================================================
# UTILITIES & IMAGE ENCODING
# =========================================================================
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.read()).decode('utf-8')

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
    headers = {
        "apikey": SUPABASE_ANON_KEY, 
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}", 
        "Content-Type": "application/json", 
        "Prefer": "on-conflict=id"
    }
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data"
    payload = {"id": st.session_state.user_id, "app_state": state_data, "updated_at": datetime.utcnow().isoformat()}
    try: 
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code not in [200, 201]:
            patch_url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{st.session_state.user_id}"
            requests.patch(patch_url, headers=headers, json={"app_state": state_data, "updated_at": datetime.utcnow().isoformat()})
    except Exception: pass

# =========================================================================
# MULTI-MODAL REASONING ENGINE (TEXT, AUDIO & VISION)
# =========================================================================
def transcribe_audio(audio_file):
    try:
        audio_data = audio_file.read()
        if not audio_data: return None
        transcript = client.audio.transcriptions.create(model="whisper-1", file=("audio.wav", audio_data, "audio/wav"))
        return transcript.text
    except Exception: return None

def process_user_input(input_text, uploaded_image=None):
    if (not input_text or input_text.strip() == "") and not uploaded_image: return

    # Startet die visuelle Nachdenk-Animation auf der Website
    with st.spinner("Überlege... 🐊"):
        now = datetime.now()
        now_str = now.strftime("%d.%m.%Y")
        wochentage_map = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        weekday_str = wochentage_map[now.weekday()]

        tasks_context = [{"id": t.get("id"), "title": t.get("title"), "summary": t.get("summary"), "type": t.get("type"), "termin": t.get("termin")} for t in st.session_state.tasks]
        grades_context = st.session_state.grades

        prompt = f"""Du bist der integrierte KI-Lerncoach für das Schüler-Board 'StudyTutor Pro'.
        Deine Aufgabe ist es, Schüler strategisch zu beraten, Noten zu tracken, hochgeladenen Stoff zu analysieren UND das Dashboard fehlerfrei zu steuern.

        HEUTIGES DATUM: {weekday_str}, der {now_str}
        Verfügbare Schulfächer: {', '.join(st.session_state.subjects)}

        Bisherige Noten des Schülers: {json.dumps(grades_context, ensure_ascii=False)}
        Aktuelle Aufgaben auf dem Board: {json.dumps(tasks_context, ensure_ascii=False)}

        User-Nachricht: "{input_text}"

        STRIKTE REGELN FÜR DIE STRUKTUR (KEINE AUTOMATISCHEN LERNPLÄNE MEHR):
        1. Wenn der User einen neuen TEST oder eine HAUSAUFGABE meldet, erstelle AUSSCHLIESSLICH diesen EINEN Eintrag mit Typ 'Test' oder 'Hausaufgabe'.
        2. Generiere NIEMALS automatisch ungefragt einen mehrtägigen Lernplan (keine Einträge mit Typ 'Lernplan' oder "Tag 1, Tag 2"-Stufen erzeugen), AUSSER der User verlangt explizit in seiner Nachricht einen Lernplan (z.B. "Erstelle mir einen Lernplan für...").
        3. Der 'summary'-Wert eines Tests/einer Hausaufgabe darf NIEMALS Bezeichnungen wie "Tag X" enthalten! Er muss sauber das Thema oder die Arbeit benennen (z.B. "Deutsch-Test" oder "Schularbeit zu Thema X").

        Antworte AUSSCHLIESSLICH im validen JSON-Format:
        {{
          "assistant_reply": "Deine persönliche, motivierende Antwort an den Schüler.",
          "tasks_to_add": [
            {{
              "title": "Fachname (MUSS exakt aus der Liste sein)",
              "type": "Test" oder "Hausaufgabe" oder "Lernplan",
              "summary": "Sauberer Titel (NUR falls explizit gewünscht mit 'Tag X:' beginnen!)",
              "prioritaet": "🚨 Hoch" oder "🟡 Mittel" oder "🟢 Niedrig",
              "termin": "DD.MM.YYYY"
            }}
          ],
          "tasks_to_delete": [],
          "grade_to_add": {{ "subject": "Fachname", "grade": 4, "note_label": "Schularbeit" }} // optional
        }}
        """

        content_payload = [{"type": "text", "text": prompt}]
        
        if uploaded_image:
            base64_image = encode_image(uploaded_image)
            content_payload.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[{"role": "user", "content": content_payload}], 
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content.strip())
            
            if result.get("grade_to_add"):
                g = result["grade_to_add"]
                st.session_state.grades.append({
                    "subject": g.get("subject"), "grade": g.get("grade"),
                    "label": g.get("note_label", "Klausur"), "date": now_str
                })

            if result.get("tasks_to_delete"):
                st.session_state.tasks = [t for t in st.session_state.tasks if t.get("id") not in result["tasks_to_delete"]]
                
            if result.get("tasks_to_add"):
                for i, t in enumerate(result["tasks_to_add"]):
                    if not any(old.get("title") == t.get("title") and old.get("summary") == t.get("summary") and old.get("termin") == t.get("termin") for old in st.session_state.tasks):
                        st.session_state.tasks.insert(0, {
                            "title": t.get("title"), "type": t.get("type", "Lernplan"), "summary": t.get("summary"),
                            "prioritaet": t.get("prioritaet", "🟡 Mittel"),
                            "notes": "Automatisch generierter KI-Lernschritt." if t.get("type") == "Lernplan" else input_text,
                            "termin": t.get("termin"), "erstellt_am": now_str, "id": f"ai_{datetime.utcnow().timestamp()}_{i}_{t.get('title')}"
                        })
            
            display_text = input_text if input_text and input_text.strip() != "" else "📸 [Bild hochgeladen]"
            st.session_state.messages.append({"role": "user", "content": display_text})
            st.session_state.messages.append({"role": "assistant", "content": result.get("assistant_reply", "Daten aktualisiert! 🐊")})
            
            save_to_supabase({
                "tasks": st.session_state.tasks, "messages": st.session_state.messages, 
                "subjects": st.session_state.subjects, "completed_count": st.session_state.get("completed_count", 0),
                "grades": st.session_state.grades
            })
        except Exception as e: 
            st.error(f"Schnittstellen Fehler: {e}")
            
    st.rerun()

# =========================================================================
# ACCOUNT-SPEZIFISCHE LIVE-INITIALISIERUNG
# =========================================================================
if "initialized_user" not in st.session_state or st.session_state.initialized_user != st.session_state.user_id:
    db_state = load_from_supabase()
    if db_state:
        st.session_state.tasks = db_state.get("tasks", [])
        st.session_state.messages = db_state.get("messages", [])
        st.session_state.subjects = db_state.get("subjects", DEFAULT_SUBJECTS)
        st.session_state.completed_count = db_state.get("completed_count", 0)
        st.session_state.grades = db_state.get("grades", [])
    else:
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": f"Hi {st.session_state.user_id}! 🐊 Ich bin dein intelligenter Mentor. Schick mir deine Noten, sprich mit mir oder fotografiere deinen Lernstoff!"}]
        st.session_state.subjects = DEFAULT_SUBJECTS
        st.session_state.completed_count = 0
        st.session_state.grades = []
    st.session_state.initialized_user = st.session_state.user_id

# =========================================================================
# SIDEBAR CONTROL CENTER
# =========================================================================
with st.sidebar:
    st.title("StudyTutor Pro 🐊")
    st.write("---")
    
    st.subheader("👥 Profil auswählen")
    try:
        current_index = st.session_state.available_profiles.index(st.session_state.user_id)
    except ValueError:
        current_index = 0
        
    selected_user = st.selectbox("Wer lernt gerade?", options=st.session_state.available_profiles, index=current_index)
    if selected_user != st.session_state.user_id:
        st.session_state.user_id = selected_user
        st.rerun()
        
    with st.expander("➕ Neues Profil anlegen"):
        new_profile_name = st.text_input("Name eingeben:", key="new_profile_input_field")
        if st.button("Konto erstellen", use_container_width=True):
            clean_name = new_profile_name.strip()
            if clean_name != "" and clean_name not in st.session_state.available_profiles:
                st.session_state.available_profiles.append(clean_name)
                st.session_state.available_profiles = sorted(st.session_state.available_profiles)
                st.session_state.user_id = clean_name
                st.success(f"Profil für {clean_name} erstellt!")
                st.rerun()
                
    st.write("---")
    st.subheader("🎯 Fokus-Modus")
    if st.session_state.tasks:
        task_options = {f"{t['title']}: {t['summary']}": t['id'] for t in st.session_state.tasks}
        selected_focus_label = st.selectbox("Wähle deine Hauptaufgabe:", ["Kein Fokus"] + list(task_options.keys()))
        selected_focus_id = task_options[selected_focus_label] if selected_focus_label != "Kein Fokus" else None
    else:
        selected_focus_id = None
        st.caption("Keine Aufgaben.")
        
    st.write("---")
    st.subheader("🔍 Filter")
    filter_subject = st.selectbox("Fach auswählen:", ["Alle Fächer"] + st.session_state.subjects)
    st.write("---")

    st.subheader("🎙️ Sprachbefehl")
    audio_file = st.audio_input("Sprachnachricht aufnehmen:")
    if audio_file and st.button("🚀 Sprache senden", use_container_width=True):
        text_from_speech = transcribe_audio(audio_file)
        if text_from_speech: process_user_input(text_from_speech)
    st.write("---")

    st.subheader("📸 Lernstoff einsenden")
    uploaded_img = st.file_uploader("Bild/Angabe hochladen:", type=["jpg", "jpeg", "png"])
    if uploaded_img and st.button("🚀 Bild abschicken", use_container_width=True):
        process_user_input("", uploaded_img)
    st.write("---")

    if st.button("🗑️ Reset", use_container_width=True):
        st.session_state.tasks = []
        st.session_state.completed_count = 0
        st.session_state.grades = []
        st.session_state.messages = [{"role": "assistant", "content": "Zurückgesetzt."}]
        save_to_supabase({"tasks": [], "messages": st.session_state.messages, "subjects": st.session_state.subjects, "completed_count": 0, "grades": []})
        st.rerun()

# =========================================================================
# MAIN CHAT
# =========================================================================
with st.expander(f"💬 KI-Lerncoach & Mentor (Konto: {st.session_state.user_id})", expanded=True):
    for msg in st.session_state.messages[-3:]:
        with st.chat_message(msg["role"]): st.write(msg["content"])
    
    chat_text = st.chat_input("Schreib mir oder nutze das Mikrofon/die Kamera links...")
    if chat_text:
        process_user_input(chat_text, uploaded_img)

# =========================================================================
# LIVE DASHBOARD STATS
# =========================================================================
stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
with stat_col1:
    st.html(f"<div class='stat-card'><div class='stat-val' style='color:#ef4444;'>{len([t for t in st.session_state.tasks if t.get('type')=='Test'])}</div><div class='stat-lbl'>OFFENE TESTS</div></div>")
with stat_col2:
    st.html(f"<div class='stat-card'><div class='stat-val' style='color:#f59e0b;'>{len([t for t in st.session_state.tasks if t.get('type')=='Hausaufgabe'])}</div><div class='stat-lbl'>HAUSAUFGABEN</div></div>")
with stat_col3:
    st.html(f"<div class='stat-card'><div class='stat-val' style='color:#10b981;'>{len([t for t in st.session_state.tasks if t.get('type')=='Lernplan'])}</div><div class='stat-lbl'>LERNPLAN SCHRITTE</div></div>")
with stat_col4:
    st.html(f"<div class='stat-card'><div class='stat-val' style='color:#3b82f6;'>{st.session_state.completed_count} ✅</div><div class='stat-lbl'>ERLEDIGT</div></div>")

# NOTENSPIEGEL
if st.session_state.grades:
    st.write(f"### 📝 Aktueller Notenspiegel von {st.session_state.user_id}")
    grade_html = ""
    for g in st.session_state.grades:
        color = "#10b981" if g['grade'] <= 2 else ("#f59e0b" if g['grade'] == 3 else "#ef4444")
        grade_html += f"<div class='grade-badge' style='border-left: 4px solid {color};'><b>{g['subject']}</b>: Note {g['grade']} <span style='font-size:0.75rem; color:#64748b;'>({g['label']})</span></div>"
    st.html(f"<div>{grade_html}</div>")

# Sniper-Fokus Box
if selected_focus_id:
    focus_task = next((t for t in st.session_state.tasks if t['id'] == selected_focus_id), None)
    if focus_task:
        st.html(f"<div class='focus-box'><div style='font-size: 0.85rem; font-weight: 700; color: #c084fc; margin-bottom: 4px;'>🎯 AKTUELLER REINZOOM-FOKUS</div><div style='font-size: 1.6rem; font-weight: 700; margin-bottom: 4px;'>{focus_task['title']} — {focus_task['summary']}</div><div>Fällig am: {focus_task.get('termin')} | Prio: {focus_task.get('prioritaet')}</div></div>")

# Filterung anwenden
active_tasks = st.session_state.tasks if filter_subject == "Alle Fächer" else [t for t in st.session_state.tasks if t.get("title") == filter_subject]

# =========================================================================
# LIVE DASHBOARD DISPLAY
# =========================================================================
st.write(f"### 📊 Workspace von {st.session_state.user_id} ({filter_subject})")
col1, col2, col3 = st.columns(3)

with col1:
    st.html("<div class='column-header'><span style='color: #ef4444;'>🔴</span> Tests & Arbeiten</div>")
    tests = [t for t in active_tasks if t.get("type") == "Test"]
    if not tests: st.caption("Keine Tests geplant. 🎉")
    for t in tests:
        st.html(f"<div class='task-card' style='border-left-color: #ef4444;'><div class='card-info-line'>📅 {t.get('termin')} | {t.get('prioritaet')}</div><div class='card-title'>{t['title']}</div><div class='card-summary'>{t['summary']}</div></div>")
        if st.button("✅ Erledigt", key=f"del_{t['id']}", use_container_width=True):
            st.session_state.tasks = [task for task in st.session_state.tasks if task['id'] != t['id']]
            st.session_state.completed_count += 1
            save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects, "completed_count": st.session_state.completed_count, "grades": st.session_state.grades})
            st.rerun()

with col2:
    st.html("<div class='column-header'><span style='color: #f59e0b;'>🟡</span> Diese & Nächste Woche</div>")
    upcoming = [t for t in active_tasks if t.get("type") in ["Hausaufgabe", "Test"] and is_within_next_fortnight(t.get("termin", ""))]
    if not upcoming: st.caption("Alles erledigt! 😎")
    for w in upcoming:
        is_test = w.get("type") == "Test"
        card_color = "#ef4444" if is_test else "#f59e0b"
        st.html(f"<div class='task-card' style='border-left-color: {card_color};'><div class='card-info-line' style='color:#b45309; background:#fef3c7;'>📅 {w.get('termin')} | {w.get('prioritaet')}</div><div class='card-title'>{w['title']}</div><div class='card-summary'>{w['summary']}</div></div>")
        if st.button("✅ Erledigt", key=f"del_up_{w['id']}", use_container_width=True):
            st.session_state.tasks = [task for task in st.session_state.tasks if task['id'] != w['id']]
            st.session_state.completed_count += 1
            save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects, "completed_count": st.session_state.completed_count, "grades": st.session_state.grades})
            st.rerun()

with col3:
    st.html("<div class='column-header'><span style='color: #10b981;'>🟢</span> Aktivierter Lernplan</div>")
    plan = [t for t in active_tasks if t.get("type") == "Lernplan"]
    if not plan: st.caption("Kein aktiver Lernplan.")
    for p in plan:
        st.html(f"<div class='task-card' style='border-left-color: #10b981;'><div class='card-info-line' style='color:#047857; background:#d1fae5;'>📅 Bis {p.get('termin')} | {p.get('prioritaet')}</div><div class='card-title'>{p['title']}</div><div class='card-summary'>{p['summary']}</div></div>")
        if st.button("✅ Schritt erledigt", key=f"del_p_{p['id']}", use_container_width=True):
            st.session_state.tasks = [task for task in st.session_state.tasks if task['id'] != p['id']]
            st.session_state.completed_count += 1
            save_to_supabase({"tasks": st.session_state.tasks, "messages": st.session_state.messages, "subjects": st.session_state.subjects, "completed_count": st.session_state.completed_count, "grades": st.session_state.grades})
            st.rerun()
