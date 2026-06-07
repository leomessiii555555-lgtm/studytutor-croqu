import streamlit as st
import openai
import requests
import json
import base64
from datetime import datetime
# HIER IST DAS NEUE MIKROFON-PAKET:
from streamlit_mic_recorder import mic_recorder

# =========================================================================
# SICHERHEITS-KONFIGURATION
# =========================================================================
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

USER_ID = "alex_soldat"
DEFAULT_SUBJECTS = ["Mathe", "Deutsch", "Englisch", "Geschichte", "Biologie", "Physik", "Chemie", "Geografie", "Informatik"]

# Page Config
st.set_page_config(page_title="StudyTutor 🐊", layout="wide", initial_sidebar_state="expanded")

# HELLLES DESIGN
st.html("""
<style>
    .stApp { background-color: #f8f9fa; color: #111111; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
        color: #111111 !important;
    }
    .dashboard-box {
        background-color: #f1f3f5;
        color: #111111;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
        border-left: 5px solid #0056b3;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .test-box { border-left-color: #dc3545; background-color: #fff5f5; }
    .week-box { border-left-color: #ffc107; background-color: #fffbeb; }
    .plan-box { border-left-color: #28a745; background-color: #f4fbf7; }
    
    div[data-testid="stChatInput"] { background-color: #ffffff; border: 1px solid #ced4da; border-radius: 20px; }
    div[data-testid="stChatInput"] textarea { color: #111111 !important; }
    
    /* Styling für den Mikrofon-Bereich */
    .mic-container { background-color: #ffffff; padding: 10px; border-radius: 10px; border: 1px solid #ced4da; margin-top: 10px; }
</style>
""")

# Hilfsfunktionen für Supabase
def load_from_supabase():
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    url = f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{USER_ID}&select=app_state"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0]['app_state']
    except:
        pass
    return None

def save_to_supabase(state_data):
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

# Sprache zu Text umwandeln mit OpenAI Whisper
def transcribe_audio(audio_bytes):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        # Temporäre Datei für das Audio erstellen
        with open("temp_audio.wav", "wb") as f:
            f.write(audio_bytes)
        
        with open("temp_audio.wav", "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        return transcript.text
    except Exception as e:
        st.error(f"Fehler bei der Spracherkennung: {str(e)}")
        return None

def extract_task_from_text(text, subjects_list):
    clean_text = text.lower()
    if "athe" in clean_text and "mathe" not in clean_text:
        clean_text = clean_text.replace("athe", "mathe")
    
    found_subject = None
    for sub in subjects_list:
        if sub.lower() in clean_text:
            found_subject = sub
            break
            
    if found_subject:
        task_type = "Hausaufgabe"
        if any(w in clean_text for w in ["test", "prüfung", "pruefung", "schularbeit", "arbeit"]):
            task_type = "Test"
        elif any(w in clean_text for w in ["ziel", "lernen", "üben", "ueben", "plan"]):
            task_type = "Lernplan"
        elif any(w in clean_text for w in ["nächste woche", "naechste woche", "woche"]):
            task_type = "Nächste Woche"
            
        return {"title": found_subject, "type": task_type, "notes": text}
    return None

# Session State initialisieren
if "initialized" not in st.session_state:
    db_state = load_from_supabase()
    if db_state:
        st.session_state.tasks = db_state.get("tasks", [])
        st.session_state.messages = db_state.get("messages", [])
        st.session_state.subjects = db_state.get("subjects", DEFAULT_SUBJECTS)
    else:
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Hallo! 🐊 Dein Lerncoach ist bereit. Du kannst jetzt tippen oder das Mikrofon benutzen!"}]
        st.session_state.subjects = DEFAULT_SUBJECTS
    st.session_state.initialized = True

# Verarbeite Eingaben (Egal ob Text oder Sprache)
user_input = None

# =========================================================================
# SIDEBAR LINKS
# =========================================================================
with st.sidebar:
    st.title("📋 Übersicht")
    st.write("---")
    
    st.subheader("🔴 Anstehende Tests")
    tests = [t for t in st.session_state.tasks if t.get("type") == "Test"]
    if not tests:
        st.caption("Keine Tests eingetragen. 🙌")
    else:
        for t in tests:
            st.html(f"<div class='dashboard-box test-box'><strong>{t['title']}</strong><br>{t['notes']}</div>")
            
    st.write("---")
    
    st.subheader("🟡 Nächste Woche")
    next_week = [t for t in st.session_state.tasks if t.get("type") == "Nächste Woche" or t.get("type") == "Hausaufgabe"]
    if not next_week:
        st.caption("Alles ruhig nächste Woche. 😎")
    else:
        for w in next_week:
            st.html(f"<div class='dashboard-box week-box'><strong>{w['title']}</strong><br>{w['notes']}</div>")
            
    st.write("---")
    
    st.subheader("🟢 Mein Lernplan")
    plan = [t for t in st.session_state.tasks if t.get("type") == "Lernplan"]
    if not plan:
        st.caption("Noch kein aktiver Lernplan.")
    else:
        for p in plan:
            st.html(f"<div class='dashboard-box plan-box'><strong>{p['title']}</strong><br>{p['notes']}</div>")

    st.write("---")
    
    with st.expander("⚙️ Tools & Stundenplan"):
        uploaded_image = st.file_uploader("Stundenplan Foto", type=["jpg", "jpeg", "png"])
        if uploaded_image and st.button("✨ Fächer einlesen"):
            with st.spinner("Lese Stundenplan..."):
                try:
                    base64_image = encode_image(uploaded_image)
                    client = openai.OpenAI(api_key=OPENAI_API_KEY)
                    img_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": [{"type": "text", "text": "Extrahiere Schulfächer als kommagetrennte Liste."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}]
                    )
                    new_subs = [s.strip() for s in img_response.choices[0].message.content.split(",") if s.strip()]
                    if new_subs:
                        st.session_state.subjects = new_subs
                        st.rerun()
                except Exception as e:
                    st.error(str(e))
                    
        if st.button("🗑️ Alle Daten löschen"):
            st.session_state.tasks = []
            save_to_supabase({"tasks": [], "messages": st.session_state.messages, "subjects": st.session_state.subjects})
            st.rerun()

# =========================================================================
# RECHTER HAUPTBEREICH (Chat & Mikrofon)
# =========================================================================
st.title("🐊 StudyTutor")
st.caption("Dein Workspace mit Tastatur- und Spracheingabe.")

# Chat-Verlauf anzeigen
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# MIKROFON UPGRADE HIER:
st.write("---")
col_mic_info, col_mic_button = st.columns([3, 1])
with col_mic_info:
    st.caption("🎤 Klicke auf 'Start recording', sprich deine Aufgabe und klicke auf 'Stop'.")
with col_mic_button:
    # Das echte Mikrofon-Widget
    audio_record = mic_recorder(start_prompt="🎤 Start", stop_prompt="🛑 Stop", key="mic")

if audio_record:
    with st.spinner("Wandle Sprache in Text um... 🎙️"):
        text_from_speech = transcribe_audio(audio_record['bytes'])
        if text_from_speech:
            user_input = text_from_speech

# Normale Chat-Eingabe (falls man tippen will)
if text_input := st.chat_input("Schreib eine neue Aufgabe oder chatte..."):
    user_input = text_input

# Wenn eine Eingabe da ist (entweder durch Tippen ODER Sprechen), verarbeiten:
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Automatisch filtern
    new_task = extract_task_from_text(user_input, st.session_state.subjects)
    if new_task:
        st.session_state.tasks.insert(0, new_task)
        
    with st.chat_message("assistant"):
        with st.spinner("..."):
            try:
                client = openai.OpenAI(api_key=OPENAI_API_KEY)
                
                sys_prompt = f"""Du bist ein minimalistischer, extrem präziser KI-Lerncoach. 
                Gib strukturierte, kurze Antworten (max. 3 Sätze). Nutze Emojis dezent.
                Beziehe dich immer auf die aktuelle Liste: {json.dumps(st.session_state.tasks)}"""
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    temperature=0.2
                )
                ai_answer = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": ai_answer})
                
                # In Datenbank sichern
                save_to_supabase({
                    "tasks": st.session_state.tasks, 
                    "messages": st.session_state.messages,
                    "subjects": st.session_state.subjects
                })
            except Exception as e:
                st.error(f"Fehler: {str(e)}")
    st.rerun()
