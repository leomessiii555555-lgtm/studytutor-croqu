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

# Page Config
st.set_page_config(page_title="StudyTutor 🐊", layout="wide", initial_sidebar_state="expanded")

# EDLES, HELLES DESIGN (Churchill-Style)
st.html("""
<style>
    .stApp { background-color: #f8f9fa; color: #111111; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
        color: #111111 !important;
    }
    
    /* Styling für die echten, sauberen Tabs/Expander links */
    .stDetails {
        border-radius: 8px !important;
        margin-bottom: 8px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    }
    
    div[data-testid="stChatInput"] { background-color: #ffffff; border: 1px solid #ced4da; border-radius: 20px; }
    div[data-testid="stChatInput"] textarea { color: #111111 !important; }
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
def transcribe_audio(audio_file):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
        return transcript.text
    except Exception as e:
        st.error(f"Fehler bei der Spracherkennung: {str(e)}")
        return None

# KI-gestützte Extraktion für saubere Titel links
def extract_task_with_ai(text, subjects_list):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""Analysiere folgenden Text und finde heraus, ob es ein Test, Lernplan oder eine Hausaufgabe/nächste Woche ist.
        Ordne es einem dieser Fächer zu: {', '.join(subjects_list)}. (Beachte Abkürzungen: 'geo' ist Geografie, 'mathe' ist Mathe).
        
        Antworte NUR mit einem gültigen JSON-Objekt im folgenden Format, ohne Codeblocks oder extra Text:
        {{"title": "Name des Fachs", "type": "Test" oder "Nächste Woche" oder "Lernplan", "summary": "Kurze, knackige Zusammenfassung der Aufgabe (max 5 Wörter)"}}
        
        Text: "{text}" """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        data = json.loads(response.choices[0].message.content.strip())
        return {
            "title": data.get("title", "Allgemein"),
            "type": data.get("type", "Nächste Woche"),
            "summary": data.get("summary", "Neue Aufgabe"),
            "notes": text
        }
    except:
        # Fallback falls KI-Analyse fehlschlägt
        return {"title": "Aufgabe", "type": "Nächste Woche", "summary": "Bitte prüfen", "notes": text}

# Session State initialisieren
if "initialized" not in st.session_state:
    db_state = load_from_supabase()
    if db_state:
        st.session_state.tasks = db_state.get("tasks", [])
        st.session_state.messages = db_state.get("messages", [])
        st.session_state.subjects = db_state.get("subjects", DEFAULT_SUBJECTS)
    else:
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Hallo! 🐊 Dein fehlerfreier Workspace ist bereit."}]
        st.session_state.subjects = DEFAULT_SUBJECTS
    st.session_state.initialized = True

user_input = None

# =========================================================================
# SIDEBAR LINKS (Dashboard mit echten Tabs / Aufklappbaren Unterpunkten)
# =========================================================================
with st.sidebar:
    st.title("📋 Übersicht")
    st.write("---")
    
    # 1. TAB: TESTS & PRÜFUNGEN
    with st.expander("🔴 Anstehende Tests", expanded=True):
        tests = [t for t in st.session_state.tasks if t.get("type") == "Test"]
        if not tests:
            st.caption("Keine Tests eingetragen. 🙌")
        else:
            for t in tests:
                # Zeigt links NUR die saubere Zusammenfassung, Details klappen auf!
                with st.popover(f"📝 {t['title']}: {t['summary']}", use_container_width=True):
                    st.write(f"**Ganzes Protokoll:** {t['notes']}")
            
    st.write("---")
    
    # 2. TAB: NÄCHSTE WOCHE
    with st.expander("🟡 Nächste Woche", expanded=True):
        next_week = [t for t in st.session_state.tasks if t.get("type") == "Nächste Woche" or t.get("type") == "Hausaufgabe"]
        if not next_week:
            st.caption("Alles ruhig nächste Woche. 😎")
        else:
            for w in next_week:
                with st.popover(f"⏳ {w['title']}: {w['summary']}", use_container_width=True):
                    st.write(f"**Ganzes Protokoll:** {w['notes']}")
            
    st.write("---")
    
    # 3. TAB: LERNPLAN
    with st.expander("🟢 Mein Lernplan", expanded=True):
        plan = [t for t in st.session_state.tasks if t.get("type") == "Lernplan"]
        if not plan:
            st.caption("Noch kein aktiver Lernplan.")
        else:
            for p in plan:
                with st.popover(f"📅 {p['title']}: {p['summary']}", use_container_width=True):
                    st.write(f"**Ganzes Protokoll:** {p['notes']}")

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
# RECHTER HAUPTBEREICH
# =========================================================================
st.title("🐊 StudyTutor")

# Chat-Verlauf
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

st.write("---")

# Audio-Eingabe (Wir nutzen dynamische Keys basierend auf der Anzahl der Nachrichten, um den Cache-Fehler zu killen!)
audio_key = f"audio_input_{len(st.session_state.messages)}"
audio_file = st.audio_input("Sprachbefehl aufnehmen", key=audio_key)

if audio_file:
    with st.spinner("Wandle Sprache in Text um... 🎙️"):
        text_from_speech = transcribe_audio(audio_file)
        if text_from_speech:
            clean_check = text_from_speech.strip().strip('.').strip().lower()
            if clean_check not in ["you", "you.", ""]:
                user_input = text_from_speech

# Normale Chat-Eingabe
if text_input := st.chat_input("Schreib eine neue Aufgabe oder chatte..."):
    user_input = text_input

# Verarbeitung
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Intelligente KI-Extraktion für den Titel links nutzen!
    with st.spinner("Sortiere Aufgabe ein..."):
        new_task = extract_task_with_ai(user_input, st.session_state.subjects)
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
                
                save_to_supabase({
                    "tasks": st.session_state.tasks, 
                    "messages": st.session_state.messages,
                    "subjects": st.session_state.subjects
                })
            except Exception as e:
                st.error(f"Fehler: {str(e)}")
    st.rerun()
