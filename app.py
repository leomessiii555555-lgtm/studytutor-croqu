import streamlit as st
import openai
import requests
import json
import base64
from datetime import datetime

# =========================================================================
# SICHERHEITS-KONFIGURATION (Holt die Keys unsichtbar aus Streamlit Secrets)
# =========================================================================
# WICHTIG: Hier im GitHub-Code darf KEIN echtes "sk-proj-..." stehen!
# Streamlit holt sich die echten Schlüssel automatisch aus deinen Secrets.
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

USER_ID = "alex_soldat"

# Standard-Fächer (falls kein Stundenplan hochgeladen wurde)
DEFAULT_SUBJECTS = ["Mathe", "Deutsch", "Englisch", "Geschichte", "Biologie", "Physik", "Chemie", "Geografie", "Informatik"]

st.set_page_config(page_title="StudyTutor 🐊", layout="wide")

# CSS Styling für ein schönes Dark-Theme (Korrigierte Version für Python 3.14)
st.html("""
<style>
    .stApp { background-color: #121214; color: #e1e1e6; }
    [data-testid="stSidebar"] { background-color: #1a1a1e; }
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

# Bild in Base64 umwandeln, damit OpenAI es lesen kann
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.read()).decode("utf-8")

# Intelligentere Extraktion für Aufgaben direkt in Python
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
        elif any(w in clean_text for w in ["ziel", "lernen", "üben", "ueben"]):
            task_type = "Lernziel"
            
        return {"title": f"{found_subject} ({task_type})", "notes": text}
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
        st.session_state.messages = [{"role": "assistant", "content": "Hallo! 🐊 Ich bin dein Lerncoach. Du kannst mir jetzt links auch ein Foto deines Stundenplans hochladen!"}]
        st.session_state.subjects = DEFAULT_SUBJECTS
    st.session_state.initialized = True

# UI Layout (Zwei Spalten)
col_chat, col_list = st.columns([2, 1])

with col_chat:
    st.title("🐊 Mein Lern-Bot")
    
    # Chat-Verlauf anzeigen
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    # Chat-Eingabe
    if user_input := st.chat_input("Schreib mir etwas..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
            
        new_task = extract_task_from_text(user_input, st.session_state.subjects)
        if new_task:
            st.session_state.tasks.insert(0, new_task)
            
        with st.chat_message("assistant"):
            with st.spinner("Ich überlege... ✍️"):
                try:
                    client = openai.OpenAI(api_key=OPENAI_API_KEY)
                    
                    sys_prompt = f"""Du bist ein schlauer KI-Lerncoach für Alex. 
                    STRENGE REGEL: Wenn der Nutzer nach Terminen, Aufgaben oder Tests fragt, lies dir das echte Aufgaben-Array unten genau durch.
                    Beziehe dich NUR auf diese Daten. Wenn die Liste leer ist, sag direkt, dass aktuell nichts eingetragen ist. Erfinde NIEMALS Aufgaben!
                    Antworte kurz (max. 3 Sätze), präzise und übersichtlich auf Deutsch mit passenden Emojis.

                    Echte Daten aus der Datenbank:
                    {json.dumps(st.session_state.tasks) if st.session_state.tasks else "LISTE IST LEER"}
                    
                    Alex hat folgende Schulfächer: {', '.join(st.session_state.subjects)}"""
                    
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user_input}
                        ],
                        temperature=0.1
                    )
                    ai_answer = response.choices[0].message.content
                    st.write(ai_answer)
                    st.session_state.messages.append({"role": "assistant", "content": ai_answer})
                    
                    # In Supabase sichern
                    current_state = {
                        "tasks": st.session_state.tasks, 
                        "messages": st.session_state.messages,
                        "subjects": st.session_state.subjects
                    }
                    save_to_supabase(current_state)
                except Exception as e:
                    st.error(f"Fehler: Verbindung fehlgeschlagen. ({str(e)})")
        st.rerun()

with col_list:
    st.header("📋 Stundenplan & Aufgaben")
    
    # STUNDENPLAN FOTO UPLOAD HIER:
    st.subheader("📅 Stundenplan hochladen")
    uploaded_image = st.file_uploader("Foto vom Stundenplan auswählen", type=["jpg", "jpeg", "png"])
    
    if uploaded_image:
        if st.button("✨ Fächer aus Stundenplan auslesen"):
            with st.spinner("Ich lese den Stundenplan... 👁️🐊"):
                try:
                    base64_image = encode_image(uploaded_image)
                    client = openai.OpenAI(api_key=OPENAI_API_KEY)
                    
                    img_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Lies dieses Bild eines Stundenplans. Extrahiere alle eindeutigen Schulfächer (z.B. Mathe, Deutsch, Biologie...) als reine, kommagetrennte Liste. Antworte NUR mit den Fächern, getrennt durch ein Komma, kein anderer Text!"},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                    }
                                ]
                            }
                        ]
                    )
                    
                    extracted_text = img_response.choices[0].message.content
                    new_subs = [s.strip() for s in extracted_text.split(",") if s.strip()]
                    if new_subs:
                        st.session_state.subjects = new_subs
                        st.success(f"Erkannte Fächer: {', '.join(new_subs)}")
                        
                        current_state = {
                            "tasks": st.session_state.tasks, 
                            "messages": st.session_state.messages,
                            "subjects": st.session_state.subjects
                        }
                        save_to_supabase(current_state)
                except Exception as e:
                    st.error(f"Fehler beim Lesen des Bildes: {str(e)}")
                    
    st.write(f"**Deine aktuellen Fächer:** {', '.join(st.session_state.subjects)}")
    st.write("---")
    
    if st.button("🗑️ Alle Aufgaben löschen"):
        st.session_state.tasks = []
        save_to_supabase({"tasks": [], "messages": st.session_state.messages, "subjects": st.session_state.subjects})
        st.rerun()
        
    st.write("---")
    
    if not st.session_state.tasks:
        st.write("Alles erledigt! 🙌")
    else:
        for task in st.session_state.tasks:
            with st.container():
                st.markdown(f"### 📝 {task.get('title')}")
                st.caption(f"Details: {task.get('notes')}")
                st.write("---")
