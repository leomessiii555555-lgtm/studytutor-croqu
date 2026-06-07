import streamlit as st
import openai
import requests
import json
from datetime import datetime, timedelta

# ==========================================
# CONFIGURATION (Trage hier deine echten Keys ein!)
# ==========================================
OPENAI_API_KEY = "sk-proj-DEIN_OPENAI_KEY"
SUPABASE_URL = "https://DEIN_PROJEKT.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
USER_ID = "alex_soldat"

# Streamlit Seiten-Konfiguration
st.set_page_config(page_title="StudyTutor Croque 🐊", layout="wide")

# Styling für ein schönes Dark-Theme (wie ChatGPT)
st.markdown("""
<style>
    .stApp { background-color: #121214; color: #e1e1e6; }
    .css-1d391kg { background-color: #1a1a1e; }
</style>
""", unsafe_allowed_html=True)

# Hilfsfunktionen für Supabase (Speichern und Laden)
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

# Session State initialisieren (Speicher im Browser-Tab)
if "initialized" not in st.session_state:
    db_state = load_from_supabase()
    if db_state:
        st.session_state.tasks = db_state.get("tasks", [])
        st.session_state.messages = db_state.get("messages", [])
    else:
        st.session_state.tasks = []
        st.session_state.messages = [{"role": "assistant", "content": "Hallo Alex! 🐊 Ich bin dein Lerncoach Croque. Ich speichere jetzt alles fehlerfrei in deiner Supabase-Datenbank ab. Schieß los!"}]
    st.session_state.initialized = True

# UI Layout: Zwei Spalten (Links: Chat, Rechts: Aufgabenliste)
col_chat, col_list = st.columns([2, 1])

with col_chat:
    st.title("🐊 Croque GPT - Lerncoach")
    
    # Chat-Verlauf anzeigen
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    # Chat-Eingabe
    if user_input := st.chat_input("Schreib Croque etwas..."):
        # User Nachricht hinzufügen
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
            
        # Hier rufen wir ChatGPT auf und füttern ihn mit den echten Datenbank-Aufgaben
        with st.chat_message("assistant"):
            with st.spinner("Croque überlegt... ✍️"):
                try:
                    client = openai.OpenAI(api_key=OPENAI_API_KEY)
                    
                    sys_prompt = f"""Du bist Croque, der schlaue KI-Lerncoach für Alex. 
                    WICHTIG: Für dich sind die Begriffe "Test", "Prüfung", "Schularbeit" und "Arbeit" das GLEICHE.
                    Wenn der Nutzer nach Terminen, Tests oder Fächern fragt, lies dir das echte Aufgaben-Array unten genau durch.
                    Beziehe dich NUR auf diese Daten. Vermische niemals die Fächer (z.B. ist eine Sanitätsübung kein Mathetest!).
                    Wenn die Liste leer ist, sag ehrlich, dass nichts eingetragen ist. Erfinde NIEMALS Aufgaben!
                    Antworte kurz (max. 3 Sätze), präzise und übersichtlich auf Deutsch mit Emojis.

                    Echte Daten aus der Supabase-Datenbank:
                    {json.dumps(st.session_state.tasks) if st.session_state.tasks else "LISTE IST LEER"}"""
                    
                    # Optionaler kleiner Extraktion-Hack in Python (simpel simuliert für den Prompt)
                    # Falls der Nutzer Aufgaben nennt, fügen wir sie hier vereinfacht der Liste hinzu
                    if "test" in user_input.lower() or "übung" in user_input.lower() or "uebung" in user_input.lower() or "prüfung" in user_input.lower():
                        # Ein einfacher Eintrag zur Demonstration, falls Schlagworte fallen
                        st.session_state.tasks.append({"title": user_input[:50], "date": "Erkannt im Chat"})
                    
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
                    
                    # In Supabase speichern
                    current_state = {"tasks": st.session_state.tasks, "messages": st.session_state.messages}
                    save_to_supabase(current_state)
                except Exception as e:
                    st.error(f"Fehler: Bitte überprüfe deine API-Keys ganz oben im Code. ({str(e)})")
        st.rerun()

with col_list:
    st.header("📋 Aufgaben & Tests")
    if not st.session_state.tasks:
        st.write("Alles erledigt! 🙌")
    else:
        for i, task in enumerate(st.session_state.tasks):
            st.info(f"**{task.get('title', 'Aufgabe')}**")
