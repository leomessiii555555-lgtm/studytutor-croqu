import streamlit as st
import openai
import requests
import json
import re
from datetime import datetime

# ==========================================
# CONFIGURATION (Trage hier deine echten Keys ein!)
# ==========================================
OPENAI_API_KEY = "sk-proj-DEIN_OPENAI_KEY"
SUPABASE_URL = "https://DEIN_PROJEKT.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
USER_ID = "alex_soldat"

# Fächerliste für die Validierung
SUBJECTS = ["Mathe", "Deutsch", "Englisch", "Geschichte", "Biologie", "Physik", "Chemie", "Geografie", "Informatik"]

st.set_page_config(page_title="StudyTutor Croque 🐊", layout="wide")

# CSS Styling für ein schönes Dark-Theme
st.markdown("""
<style>
    .stApp { background-color: #121214; color: #e1e1e6; }
    [data-testid="stSidebar"] { background-color: #1a1a1e; }
</style>
""", unsafe_allowed_html=True)

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

# Intelligentere Extraktion für Aufgaben direkt in Python
def extract_task_from_text(text):
    clean_text = text.lower()
    # Behebt den Tippfehler ",athe" -> "mathe"
    if "athe" in clean_text and "mathe" not in clean_text:
        clean_text = clean_text.replace("athe", "mathe")
    
    # Prüfen, welches Fach erwähnt wurde
    found_subject = None
    for sub in SUBJECTS:
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
    else:
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Hallo Alex! 🐊 Ich bin dein Lerncoach Croque. Schreib mir einfach, was in der Schule ansteht!"}]
    st.session_state.initialized = True

# UI Layout
col_chat, col_list = st.columns([2, 1])

with col_chat:
    st.title("🐊 Croque GPT - Lerncoach")
    
    # Chat-Verlauf anzeigen
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    # Chat-Eingabe
    if user_input := st.chat_input("Schreib Croque etwas..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
            
        # Task-Extraktion triggern bevor ChatGPT antwortet
        new_task = extract_task_from_text(user_input)
        if new_task:
            st.session_state.tasks.insert(0, new_task)
            
        with st.chat_message("assistant"):
            with st.spinner("Croque überlegt... ✍️"):
                try:
                    client = openai.OpenAI(api_key=OPENAI_API_KEY)
                    
                    sys_prompt = f"""Du bist Croque, der schlaue KI-Lerncoach für Alex. 
                    STRENGE REGEL: Wenn der Nutzer nach Terminen, Aufgaben oder Tests fragt, lies dir das echte Aufgaben-Array unten genau durch.
                    Beziehe dich NUR auf diese Daten. Wenn die Liste leer ist, sag direkt, dass aktuell nichts eingetragen ist. Erfinde NIEMALS Aufgaben!
                    Antworte kurz (max. 3 Sätze), präzise und übersichtlich auf Deutsch mit passenden Emojis.

                    Echte Daten aus der Datenbank:
                    {json.dumps(st.session_state.tasks) if st.session_state.tasks else "LISTE IST LEER"}"""
                    
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
                    current_state = {"tasks": st.session_state.tasks, "messages": st.session_state.messages}
                    save_to_supabase(current_state)
                except Exception as e:
                    st.error(f"Fehler: Verbindung zu OpenAI oder Supabase fehlgeschlagen. ({str(e)})")
        st.rerun()

with col_list:
    st.header("📋 Aufgaben & Tests")
    
    # Button zum Zurücksetzen der Liste (falls man aufräumen will)
    if st.button("🗑️ Alle Aufgaben löschen"):
        st.session_state.tasks = []
        save_to_supabase({"tasks": [], "messages": st.session_state.messages})
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
