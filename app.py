import base64
import html
import io
import json
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta
from urllib.parse import quote

import openai
import requests
import streamlit as st
from PIL import Image

try:
    import piheif

    piheif.register_heif_opener()
except ImportError:
    pass


# ============================================================================
# CONFIG
# ============================================================================
APP_NAME = "StudyTutor Pro"
APP_ICON = "🐊"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DEFAULT_SUBJECTS = [
    "Mathe",
    "Deutsch",
    "Englisch",
    "Spanisch",
    "Geschichte",
    "Biologie",
    "Physik",
    "Chemie",
    "Geografie",
    "Informatik",
]

LEITNER_INTERVALS = {
    1: 0,
    2: 1,
    3: 3,
    4: 7,
    5: 14,
    6: 30,
}

GRADE_LABELS = ["Schularbeit (SA)", "Test", "Mitarbeit"]


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return os.getenv(name, value) or default


OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
SUPABASE_URL = get_secret("SUPABASE_URL").rstrip("/")
SUPABASE_ANON_KEY = get_secret("SUPABASE_ANON_KEY")

client = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

st.set_page_config(
    page_title=f"{APP_NAME} {APP_ICON}",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# UI HELPERS
# ============================================================================
def html_block(markup: str) -> None:
    if hasattr(st, "html"):
        st.html(markup)
    else:
        st.markdown(markup, unsafe_allow_html=True)


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def voice_input(label: str, key: str, label_visibility: str = "visible"):
    if hasattr(st, "audio_input"):
        return st.audio_input(label, key=key, label_visibility=label_visibility)
    return st.file_uploader(
        label,
        type=["wav", "mp3", "m4a", "ogg", "webm"],
        key=key,
        label_visibility=label_visibility,
    )


def toast_success(text: str) -> None:
    if hasattr(st, "toast"):
        st.toast(text)
    else:
        st.success(text)


html_block(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --bg: #f7f8fb;
        --panel: #ffffff;
        --panel-2: #f1f5f9;
        --text: #102033;
        --muted: #617086;
        --line: #dbe3ee;
        --blue: #2563eb;
        --green: #059669;
        --amber: #d97706;
        --rose: #e11d48;
        --violet: #7c3aed;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
        font-family: 'Inter', sans-serif;
    }

    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--line);
    }

    .hero-band {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
        padding: 18px 20px;
        margin-bottom: 18px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: linear-gradient(120deg, #ffffff 0%, #eef6ff 55%, #ecfdf5 100%);
    }

    .hero-title {
        margin: 0;
        color: var(--text);
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: 0;
    }

    .hero-copy {
        margin: 4px 0 0 0;
        color: var(--muted);
        font-size: .95rem;
        font-weight: 500;
    }

    .stat-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 18px;
    }

    .stat-card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px 16px;
    }

    .stat-value {
        color: var(--text);
        font-size: 1.45rem;
        font-weight: 800;
        line-height: 1.15;
    }

    .stat-label {
        color: var(--muted);
        font-size: .78rem;
        font-weight: 700;
        text-transform: uppercase;
        margin-top: 3px;
    }

    .calendar-wrap {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
    }

    .calendar-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        color: var(--text);
        font-weight: 800;
    }

    .calendar-day-name {
        color: var(--muted);
        font-size: .76rem;
        font-weight: 800;
        text-transform: uppercase;
        margin-bottom: 6px;
    }

    .calendar-cell {
        min-height: 116px;
        background: #f8fafc;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 10px;
        overflow: hidden;
    }

    .calendar-cell.today {
        background: #eff6ff;
        border: 2px solid var(--blue);
    }

    .calendar-date {
        color: var(--text);
        font-weight: 800;
        margin-bottom: 8px;
    }

    .event-pill {
        display: block;
        padding: 4px 7px;
        border-radius: 6px;
        color: #ffffff;
        font-size: .72rem;
        font-weight: 800;
        margin: 4px 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .section-title {
        color: var(--text);
        font-size: 1.05rem;
        font-weight: 800;
        margin: 14px 0 10px 0;
    }

    .task-card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-left: 5px solid var(--rose);
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 8px;
    }

    .task-card.homework {
        border-left-color: var(--amber);
    }

    .task-card.overdue {
        background: #fff1f2;
    }

    .task-meta {
        display: inline-block;
        background: #eaf2ff;
        color: #1d4ed8;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: .76rem;
        font-weight: 800;
        margin-bottom: 8px;
    }

    .task-title {
        color: var(--text);
        font-weight: 800;
        font-size: 1.02rem;
        margin-bottom: 3px;
    }

    .task-summary {
        color: var(--muted);
        font-weight: 600;
        font-size: .92rem;
    }

    .flashcard-box {
        min-height: 240px;
        border-radius: 8px;
        padding: 28px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        background: linear-gradient(135deg, #2563eb 0%, #0891b2 100%);
        color: #ffffff;
        box-shadow: 0 20px 42px rgba(37, 99, 235, .18);
    }

    .flashcard-box.flipped {
        background: linear-gradient(135deg, #059669 0%, #0f766e 100%);
    }

    .flashcard-label {
        font-size: .78rem;
        font-weight: 800;
        text-transform: uppercase;
        opacity: .86;
        margin-bottom: 12px;
    }

    .flashcard-text {
        font-size: 1.35rem;
        font-weight: 800;
        line-height: 1.38;
    }

    .grade-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 34px;
        height: 34px;
        border-radius: 8px;
        background: #ecfeff;
        border: 1px solid #a5f3fc;
        color: #155e75;
        font-weight: 900;
        margin-right: 8px;
    }

    .gaming-shell {
        background: #0f172a;
        color: #f8fafc;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 22px;
        margin-bottom: 18px;
    }

    .quest-card {
        background: rgba(15, 23, 42, .68);
        border: 1px solid #38bdf8;
        border-left: 5px solid #38bdf8;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 8px;
        color: #e2e8f0;
    }

    .quest-card.locked {
        opacity: .45;
        border-color: #64748b;
        border-left-color: #64748b;
    }

    .quest-card.active {
        border-color: #a78bfa;
        border-left-color: #a78bfa;
        background: rgba(49, 46, 129, .42);
    }

    .error-box {
        background: #fff7ed;
        border: 1px dashed #f97316;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 10px;
    }

    @media (max-width: 900px) {
        .stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .hero-band { align-items: flex-start; flex-direction: column; }
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --bg: #0b1120;
            --panel: #111827;
            --panel-2: #1f2937;
            --text: #f8fafc;
            --muted: #cbd5e1;
            --line: #334155;
        }
        .hero-band {
            background: linear-gradient(120deg, #111827 0%, #172554 55%, #064e3b 100%);
        }
        .calendar-cell { background: #0f172a; }
        .calendar-cell.today { background: #172554; }
        .task-card.overdue { background: #3f111d; }
        .task-meta { background: #172554; color: #bfdbfe; }
        .error-box { background: #2b1b0f; border-color: #fb923c; }
    }
</style>
"""
)

html_block(
    """
<script>
    if (Notification.permission !== "granted" && Notification.permission !== "denied") {
        Notification.requestPermission();
    }
    window.sendStudyTutorNotification = function(title, body) {
        if (Notification.permission === "granted") {
            new Notification(title, { body: body, icon: "https://emojicdn.elk.sh/🐊" });
        }
    };
</script>
"""
)


# ============================================================================
# STATE
# ============================================================================
def default_state():
    return {
        "xp": 0,
        "streak": 0,
        "last_study_date": "",
        "completed_count": 0,
        "tasks": [],
        "messages": [],
        "subjects": list(DEFAULT_SUBJECTS),
        "grades": [],
        "flashcards": [],
        "card_flipped": False,
        "card_idx": 0,
        "notified_task_ids": [],
        "gaming_quests": [],
        "kuckuckseier": [],
        "handwriting_analysis": "",
        "active_summary": "",
        "calendar_week_offset": 0,
    }


def ensure_state_defaults() -> None:
    for key, value in default_state().items():
        if key not in st.session_state:
            st.session_state[key] = value


ensure_state_defaults()


# ============================================================================
# DATE, AUDIO, IMAGE AND AI UTILITIES
# ============================================================================
def today_date() -> date:
    return datetime.now().date()


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", str(value))
    if not match:
        return None
    try:
        return datetime.strptime(match.group(0), "%d.%m.%Y").date()
    except ValueError:
        return None


def days_left(termin: str) -> int | None:
    due = parse_date(termin)
    if not due:
        return None
    return (due - today_date()).days


def due_label(termin: str) -> str:
    left = days_left(termin)
    if left is None:
        return "ohne Datum"
    if left < 0:
        return f"{abs(left)} Tag(e) überfällig"
    if left == 0:
        return "heute fällig"
    if left == 1:
        return "morgen fällig"
    return f"in {left} Tagen"


def priority_rank(task: dict) -> int:
    priority = str(task.get("prioritaet", ""))
    if "Hoch" in priority or "🚨" in priority:
        return 0
    return 1


def sorted_tasks(tasks: list[dict]) -> list[dict]:
    return sorted(
        tasks,
        key=lambda item: (
            parse_date(item.get("termin")) or date.max,
            priority_rank(item),
            str(item.get("title", "")),
        ),
    )


def get_level() -> int:
    return int(st.session_state.xp // 100) + 1


def next_task_id(prefix: str = "task") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def encode_image(uploaded_file) -> str | None:
    try:
        image = Image.open(uploaded_file)
        if image.mode in ("RGBA", "P", "CMYK"):
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=92)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")
    except Exception as exc:
        st.error(f"Bild konnte nicht verarbeitet werden: {exc}")
        return None


def transcribe_audio(audio_file) -> str | None:
    if not audio_file or not client:
        return None
    try:
        audio_data = audio_file.read()
        if not audio_data:
            return None
        mime_type = getattr(audio_file, "type", "audio/wav") or "audio/wav"
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio_input.wav", audio_data, mime_type),
        )
        return transcript.text
    except Exception as exc:
        st.warning(f"Audio konnte nicht transkribiert werden: {exc}")
        return None


def parse_ai_json(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def ai_json_request(messages: list[dict], temperature: float = 0.2) -> dict | None:
    if not client:
        st.warning("OpenAI ist noch nicht konfiguriert. Bitte OPENAI_API_KEY in den Secrets hinterlegen.")
        return None
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        return parse_ai_json(response.choices[0].message.content.strip())
    except Exception as exc:
        st.error(f"KI-Antwort konnte nicht verarbeitet werden: {exc}")
        return None


def ai_text_request(prompt: str, temperature: float = 0.3) -> str | None:
    if not client:
        st.warning("OpenAI ist noch nicht konfiguriert. Bitte OPENAI_API_KEY in den Secrets hinterlegen.")
        return None
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        st.error(f"KI-Antwort fehlgeschlagen: {exc}")
        return None


# ============================================================================
# SUPABASE
# ============================================================================
def supabase_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


def supabase_headers(extra: dict | None = None) -> dict:
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def get_all_registered_profiles() -> list[str]:
    if not supabase_ready():
        return ["Alex"]
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/studytutor_data?select=id",
            headers=supabase_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            profiles = [row["id"] for row in response.json() if row.get("id")]
            if "Alex" not in profiles:
                profiles.insert(0, "Alex")
            return sorted(set(profiles))
    except Exception:
        pass
    return ["Alex"]


def normalize_loaded_state(db_state) -> dict | None:
    if not db_state:
        return None
    if isinstance(db_state, str):
        try:
            db_state = json.loads(db_state)
        except json.JSONDecodeError:
            return None
    if not isinstance(db_state, dict):
        return None
    merged = default_state()
    merged.update(db_state)
    if not merged.get("subjects"):
        merged["subjects"] = list(DEFAULT_SUBJECTS)

    for task in merged.get("tasks", []):
        if isinstance(task, dict):
            task.setdefault("id", next_task_id("task"))
            task.setdefault("created_at", datetime.utcnow().isoformat())

    for card in merged.get("flashcards", []):
        if isinstance(card, dict):
            card.setdefault("id", next_task_id("card"))
            card.setdefault("box", 1)
            card.setdefault("next_due", format_date(today_date()))
            card.setdefault("correct_count", 0)

    return merged


def load_from_supabase() -> dict | None:
    if not supabase_ready():
        return None
    user_id = st.session_state.user_id
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{quote(str(user_id), safe='')}&select=app_state",
            headers=supabase_headers(),
            timeout=10,
        )
        if response.status_code == 200 and response.json():
            return normalize_loaded_state(response.json()[0].get("app_state"))
    except Exception:
        pass
    return None


def save_to_supabase(state_data: dict) -> None:
    if not supabase_ready() or not state_data:
        return
    payload = {
        "id": st.session_state.user_id,
        "app_state": state_data,
        "updated_at": datetime.utcnow().isoformat(),
    }
    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/studytutor_data",
            headers=supabase_headers({"Prefer": "resolution=merge-duplicates"}),
            json=payload,
            timeout=10,
        )
        if response.status_code not in (200, 201):
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{quote(str(st.session_state.user_id), safe='')}",
                headers=supabase_headers(),
                json={
                    "app_state": state_data,
                    "updated_at": datetime.utcnow().isoformat(),
                },
                timeout=10,
            )
    except Exception:
        pass


def delete_profile_from_supabase(profile_id: str) -> None:
    if not supabase_ready() or not profile_id:
        return
    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/studytutor_data?id=eq.{quote(str(profile_id), safe='')}",
            headers=supabase_headers(),
            timeout=10,
        )
    except Exception:
        pass


def current_state_for_save() -> dict:
    keys = [
        "tasks",
        "messages",
        "subjects",
        "completed_count",
        "grades",
        "xp",
        "streak",
        "last_study_date",
        "flashcards",
        "gaming_quests",
        "kuckuckseier",
        "handwriting_analysis",
        "active_summary",
        "notified_task_ids",
    ]
    return {key: st.session_state.get(key, default_state().get(key)) for key in keys}


def save_all_to_db() -> None:
    save_to_supabase(current_state_for_save())


if "available_profiles" not in st.session_state:
    st.session_state.available_profiles = get_all_registered_profiles()

if "user_id" not in st.session_state:
    st.session_state.user_id = st.session_state.available_profiles[0]


def load_profile_if_needed() -> None:
    if st.session_state.get("initialized_user") == st.session_state.user_id:
        return

    loaded_state = load_from_supabase()
    if loaded_state:
        for key, value in loaded_state.items():
            st.session_state[key] = value
    else:
        for key, value in default_state().items():
            st.session_state[key] = value
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": f"Hi {st.session_state.user_id}! Ich bin bereit. Was steht heute an?",
            }
        ]

    st.session_state.initialized_user = st.session_state.user_id


load_profile_if_needed()


# ============================================================================
# DOMAIN ACTIONS
# ============================================================================
def normalize_task(raw: dict) -> dict:
    task_type = raw.get("type", "Hausaufgabe")
    if task_type not in ["Test", "Hausaufgabe"]:
        task_type = "Test" if "test" in str(task_type).lower() else "Hausaufgabe"

    due = parse_date(raw.get("termin"))
    due_text = format_date(due) if due else format_date(today_date())

    return {
        "id": raw.get("id") or next_task_id("ai"),
        "title": str(raw.get("title") or raw.get("subject") or "Allgemein").strip(),
        "type": task_type,
        "summary": str(raw.get("summary") or raw.get("description") or "Ohne Thema").strip(),
        "prioritaet": raw.get("prioritaet") if raw.get("prioritaet") in ["🚨 Hoch", "🟡 Mittel"] else "🟡 Mittel",
        "termin": due_text,
        "created_at": raw.get("created_at") or datetime.utcnow().isoformat(),
    }


def add_task(raw: dict) -> None:
    task = normalize_task(raw)
    st.session_state.tasks.insert(0, task)


def add_flashcard(raw: dict) -> bool:
    question = str(raw.get("question", "")).strip()
    answer = str(raw.get("answer", "")).strip()
    if not question or not answer:
        return False
    st.session_state.flashcards.append(
        {
            "id": raw.get("id") or next_task_id("card"),
            "subject": raw.get("subject") or raw.get("title") or "Allgemein",
            "question": question,
            "answer": answer,
            "box": int(raw.get("box", 1) or 1),
            "next_due": raw.get("next_due") or format_date(today_date()),
            "correct_count": int(raw.get("correct_count", 0) or 0),
        }
    )
    return True


def add_grade(raw: dict) -> bool:
    try:
        grade_value = float(raw.get("grade"))
    except (TypeError, ValueError):
        return False
    if grade_value < 1 or grade_value > 5:
        return False

    label = raw.get("label") if raw.get("label") in GRADE_LABELS else "Test"
    st.session_state.grades.append(
        {
            "subject": raw.get("subject") or "Allgemein",
            "grade": grade_value,
            "label": label,
            "desc": raw.get("desc") or raw.get("description") or label,
            "date": raw.get("date") or format_date(today_date()),
        }
    )
    return True


def bump_streak() -> None:
    today_text = format_date(today_date())
    yesterday_text = format_date(today_date() - timedelta(days=1))
    last_day = st.session_state.get("last_study_date", "")

    if last_day == today_text:
        return
    if last_day == yesterday_text:
        st.session_state.streak += 1
    else:
        st.session_state.streak = 1
    st.session_state.last_study_date = today_text


def complete_task(task_id: str, xp: int) -> None:
    st.session_state.tasks = [task for task in st.session_state.tasks if task.get("id") != task_id]
    st.session_state.xp += xp
    st.session_state.completed_count += 1
    bump_streak()
    save_all_to_db()


def trigger_browser_notification(title: str, text: str) -> None:
    html_block(
        f"<script>window.sendStudyTutorNotification({json.dumps(title)}, {json.dumps(text)});</script>"
    )


def check_and_send_deadline_notifications() -> None:
    for task in st.session_state.tasks:
        task_id = task.get("id")
        if not task_id or task_id in st.session_state.notified_task_ids:
            continue
        remaining = days_left(task.get("termin"))
        if remaining is not None and 0 <= remaining <= 2:
            when = "ist heute fällig" if remaining == 0 else "ist morgen fällig" if remaining == 1 else f"ist in {remaining} Tagen fällig"
            trigger_browser_notification(
                f"{APP_NAME} Erinnerung",
                f"{task.get('type', 'Aufgabe')} in {task.get('title', 'Allgemein')}: {task.get('summary', '')} {when}.",
            )
            st.session_state.notified_task_ids.append(task_id)
    save_all_to_db()


def calculate_subject_average(subject: str) -> tuple[float | None, str]:
    grades = [grade for grade in st.session_state.grades if grade.get("subject") == subject]
    if not grades:
        return None, "Keine Noten"

    sa = [grade["grade"] for grade in grades if grade.get("label") == "Schularbeit (SA)"]
    tests = [grade["grade"] for grade in grades if grade.get("label") == "Test"]
    oral = [grade["grade"] for grade in grades if grade.get("label") == "Mitarbeit"]

    has_sa, has_tests, has_oral = bool(sa), bool(tests), bool(oral)
    if has_sa and has_tests and has_oral:
        avg = (sum(sa) / len(sa)) * 0.50 + (sum(tests) / len(tests)) * 0.25 + (sum(oral) / len(oral)) * 0.25
        return avg, "SA 50%, Test 25%, Mitarbeit 25%"
    if has_sa and has_tests:
        avg = (sum(sa) / len(sa)) * 0.65 + (sum(tests) / len(tests)) * 0.35
        return avg, "SA 65%, Test 35%"
    if has_sa and has_oral:
        avg = (sum(sa) / len(sa)) * 0.60 + (sum(oral) / len(oral)) * 0.40
        return avg, "SA 60%, Mitarbeit 40%"
    if has_tests and has_oral:
        avg = (sum(tests) / len(tests)) * 0.50 + (sum(oral) / len(oral)) * 0.50
        return avg, "Test 50%, Mitarbeit 50%"

    values = [grade["grade"] for grade in grades]
    return sum(values) / len(values), "Bisher eine Kategorie"


def overall_grade_average() -> str:
    avgs = [calculate_subject_average(subject)[0] for subject in st.session_state.subjects]
    clean = [avg for avg in avgs if avg is not None]
    if not clean:
        return "–"
    return f"{sum(clean) / len(clean):.2f}"


# ============================================================================
# CORE AI COACH
# ============================================================================
def coach_prompt(input_text: str) -> str:
    now = datetime.now()
    now_text = now.strftime("%d.%m.%Y")
    weekday = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][now.weekday()]

    handwriting = st.session_state.get("handwriting_analysis", "")
    handwriting_note = (
        f"\nHandschriftprofil des Schülers für Bildauswertung: {handwriting}\n" if handwriting else ""
    )

    return f"""
Du bist der integrierte KI-Lerncoach in StudyTutor Pro. Handle wie ein präziser Schulplaner,
ein motivierender Tutor und ein ruhiger Lerncoach.

HEUTIGES DATUM:
- Heute ist {weekday}, der {now_text}.
- Relative Datumsangaben müssen mathematisch exakt von diesem Datum aus berechnet werden.
- Jedes Datum im JSON muss im Format DD.MM.YYYY stehen.
- Erfinde kein Datum, wenn der User keines nennt. Frage dann in assistant_reply kurz nach.

FEATURES, DIE DU STEUERN DARFST:
- Aufgaben und Tests anlegen.
- Aufgaben anhand der vorhandenen IDs löschen.
- Einzelne Noten eintragen.
- Karteikarten erzeugen.
- Sinnvoll antworten, ohne unnötige Aktionen auszuführen.

REGELN:
- Antworte ausschließlich als valides JSON.
- Nutze nur diese Fächer, außer der User nennt ausdrücklich ein neues Fach:
  {json.dumps(st.session_state.subjects, ensure_ascii=False)}
- Aufgabe-Typ ist nur "Test" oder "Hausaufgabe".
- prioritaet ist nur "🚨 Hoch" oder "🟡 Mittel".
- Wenn der User löschen/entfernen/abhaken sagt, schreibe die passenden IDs in tasks_to_delete.
- Wenn du unsicher bist, ändere keine Daten und frage in assistant_reply kurz nach.
{handwriting_note}
AKTUELLE AUFGABEN:
{json.dumps(st.session_state.tasks, ensure_ascii=False)}

USER:
{input_text}

JSON-SCHEMA:
{{
  "assistant_reply": "kurze, persönliche Antwort an den Schüler",
  "tasks_to_add": [
    {{
      "title": "Fachname",
      "type": "Test oder Hausaufgabe",
      "summary": "Thema",
      "prioritaet": "🚨 Hoch oder 🟡 Mittel",
      "termin": "DD.MM.YYYY"
    }}
  ],
  "tasks_to_delete": ["task_id"],
  "grade_to_add": {{
    "subject": "Fachname",
    "grade": 1,
    "label": "Schularbeit (SA) oder Test oder Mitarbeit",
    "desc": "Beschreibung"
  }},
  "flashcards_to_add": [
    {{
      "subject": "Fachname",
      "question": "Frage",
      "answer": "Antwort"
    }}
  ],
  "subjects_to_add": ["Neues Fach"]
}}
"""


def process_user_input(input_text: str, uploaded_image=None) -> None:
    if (not input_text or not input_text.strip()) and not uploaded_image:
        return

    final_text = input_text.strip() if input_text else ""

    with st.spinner("Kroko denkt mit..."):
        content_payload = [{"type": "text", "text": coach_prompt(final_text)}]
        if uploaded_image:
            image_code = encode_image(uploaded_image)
            if image_code:
                content_payload.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_code}"}}
                )

        result = ai_json_request([{"role": "user", "content": content_payload}], temperature=0.0)
        if not result:
            return

        for subject in result.get("subjects_to_add", []) or []:
            subject_name = str(subject).strip()
            if subject_name and subject_name not in st.session_state.subjects:
                st.session_state.subjects.append(subject_name)

        for task in result.get("tasks_to_add", []) or []:
            add_task(task)

        delete_ids = set(result.get("tasks_to_delete", []) or [])
        if delete_ids:
            st.session_state.tasks = [task for task in st.session_state.tasks if task.get("id") not in delete_ids]

        grade_payload = result.get("grade_to_add")
        if isinstance(grade_payload, dict):
            add_grade(grade_payload)

        for card in result.get("flashcards_to_add", []) or []:
            add_flashcard(card)

        user_message = final_text if final_text else "[Bild hochgeladen]"
        if uploaded_image and final_text:
            user_message = f"{final_text} [Bild hochgeladen]"

        st.session_state.messages.append({"role": "user", "content": user_message})
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result.get("assistant_reply", "Erledigt. Ich habe dein Board aktualisiert."),
            }
        )
        save_all_to_db()

    rerun()


check_and_send_deadline_notifications()


# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.title(f"{APP_NAME} {APP_ICON}")
    st.caption("Lerncoach, Planer, Karten, Noten und Fokusmodus.")

    if "app_mode" not in st.session_state:
        st.session_state.app_mode = "Dashboard"

    modes = [
        ("Dashboard", "📊 Dashboard"),
        ("Karteikarten", "🃏 Karteikarten"),
        ("Notenspiegel", "📝 Notenspiegel"),
        ("Lernzentrum", "🎯 Lernzentrum"),
    ]
    for mode_key, label in modes:
        if st.button(
            label,
            use_container_width=True,
            type="primary" if st.session_state.app_mode == mode_key else "secondary",
        ):
            st.session_state.app_mode = mode_key
            rerun()

    st.divider()
    st.subheader("Dein Fortschritt")
    level = get_level()
    st.write(f"**Level {level}** · {st.session_state.xp % 100}/100 XP")
    st.progress((st.session_state.xp % 100) / 100)
    st.write(f"🔥 **Lern-Streak:** {st.session_state.streak} Tag(e)")
    st.write(f"✅ **Erledigt:** {st.session_state.completed_count}")

    st.divider()
    st.subheader("Profil")
    if st.session_state.user_id not in st.session_state.available_profiles:
        st.session_state.available_profiles.append(st.session_state.user_id)
    st.session_state.available_profiles = sorted(set(st.session_state.available_profiles))

    selected_user = st.selectbox(
        "Profil wechseln",
        options=st.session_state.available_profiles,
        index=st.session_state.available_profiles.index(st.session_state.user_id),
    )
    if selected_user != st.session_state.user_id:
        st.session_state.user_id = selected_user
        rerun()

    with st.expander("Profile verwalten"):
        new_profile_name = st.text_input("Neues Profil", placeholder="Name")
        new_profile_audio = voice_input("Name einsprechen", key="aud_profile_name")
        if st.button("Profil anlegen", use_container_width=True):
            final_name = new_profile_name.strip() if new_profile_name else ""
            if new_profile_audio:
                spoken_name = transcribe_audio(new_profile_audio)
                if spoken_name:
                    final_name = spoken_name.replace(".", "").strip()
            if final_name and final_name not in st.session_state.available_profiles:
                st.session_state.available_profiles.append(final_name)
                st.session_state.user_id = final_name
                fresh_state = default_state()
                fresh_state["messages"] = [
                    {
                        "role": "assistant",
                        "content": f"Hi {final_name}! Dein neues Profil ist bereit.",
                    }
                ]
                for key, value in fresh_state.items():
                    st.session_state[key] = value
                st.session_state.initialized_user = final_name
                save_all_to_db()
                rerun()

        if st.session_state.user_id != "Alex":
            if st.button("Aktuelles Profil löschen", use_container_width=True):
                delete_profile_from_supabase(st.session_state.user_id)
                st.session_state.available_profiles = [
                    profile for profile in st.session_state.available_profiles if profile != st.session_state.user_id
                ] or ["Alex"]
                st.session_state.user_id = st.session_state.available_profiles[0]
                st.session_state.initialized_user = None
                rerun()

    with st.expander("Fächer verwalten"):
        new_subject = st.text_input("Fach hinzufügen")
        if st.button("Fach speichern", use_container_width=True):
            subject = new_subject.strip()
            if subject and subject not in st.session_state.subjects:
                st.session_state.subjects.append(subject)
                save_all_to_db()
                rerun()
        remove_subject = st.selectbox("Fach entfernen", [""] + st.session_state.subjects)
        if remove_subject and st.button("Aus Liste entfernen", use_container_width=True):
            if len(st.session_state.subjects) <= 1:
                st.warning("Mindestens ein Fach muss erhalten bleiben.")
            else:
                st.session_state.subjects = [subject for subject in st.session_state.subjects if subject != remove_subject]
                save_all_to_db()
                rerun()

    st.divider()
    st.caption(
        "OpenAI: verbunden" if OPENAI_API_KEY else "OpenAI: Secret fehlt"
    )
    st.caption(
        "Supabase: verbunden" if supabase_ready() else "Supabase: lokal ohne Sync"
    )


# ============================================================================
# DASHBOARD
# ============================================================================
def render_stats() -> None:
    upcoming = [
        task
        for task in st.session_state.tasks
        if days_left(task.get("termin")) is not None and days_left(task.get("termin")) <= 2
    ]
    html_block(
        f"""
<div class="stat-grid">
  <div class="stat-card"><div class="stat-value">{len(st.session_state.tasks)}</div><div class="stat-label">Offene Aufgaben</div></div>
  <div class="stat-card"><div class="stat-value">{len(upcoming)}</div><div class="stat-label">Bis in 2 Tagen</div></div>
  <div class="stat-card"><div class="stat-value">{len(st.session_state.flashcards)}</div><div class="stat-label">Karteikarten</div></div>
  <div class="stat-card"><div class="stat-value">{overall_grade_average()}</div><div class="stat-label">Notenstand</div></div>
</div>
"""
    )


def render_calendar() -> None:
    today = today_date()
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=st.session_state.calendar_week_offset)
    week_end = week_start + timedelta(days=6)

    nav_left, nav_mid, nav_right = st.columns([1, 4, 1])
    with nav_left:
        if st.button("← Woche", use_container_width=True):
            st.session_state.calendar_week_offset -= 1
            rerun()
    with nav_mid:
        if st.button(f"{format_date(week_start)} bis {format_date(week_end)} · Heute anzeigen", use_container_width=True):
            st.session_state.calendar_week_offset = 0
            rerun()
    with nav_right:
        if st.button("Woche →", use_container_width=True):
            st.session_state.calendar_week_offset += 1
            rerun()

    html_block("<div class='calendar-wrap'><div class='calendar-head'><span>Smarter Wochenkalender</span><span>Tests rot · Hausaufgaben gelb</span></div>")
    day_names = ["MO", "DI", "MI", "DO", "FR", "SA", "SO"]
    cols = st.columns(7)
    for idx, col in enumerate(cols):
        current_day = week_start + timedelta(days=idx)
        current_text = format_date(current_day)
        classes = "calendar-cell today" if current_day == today else "calendar-cell"
        events = ""
        for task in sorted_tasks(st.session_state.tasks):
            if task.get("termin") == current_text:
                color = "#e11d48" if task.get("type") == "Test" else "#d97706"
                events += (
                    f"<span class='event-pill' style='background:{color};'>"
                    f"{esc(task.get('title'))}: {esc(task.get('summary'))}</span>"
                )
        if not events:
            events = "<span style='color:#94a3b8;font-size:.78rem;font-weight:700;'>frei</span>"
        col.markdown(
            f"""
<div class="calendar-day-name">{day_names[idx]}</div>
<div class="{classes}">
  <div class="calendar-date">{current_day.day}</div>
  {events}
</div>
""",
            unsafe_allow_html=True,
        )
    html_block("</div>")


def render_task_card(task: dict, xp_reward: int) -> None:
    task_id = task.get("id")
    overdue_class = " overdue" if (days_left(task.get("termin")) is not None and days_left(task.get("termin")) < 0) else ""
    homework_class = " homework" if task.get("type") == "Hausaufgabe" else ""
    html_block(
        f"""
<div class="task-card{homework_class}{overdue_class}">
  <div class="task-meta">{esc(task.get("termin"))} · {esc(due_label(task.get("termin")))} · {esc(task.get("prioritaet"))}</div>
  <div class="task-title">{esc(task.get("title"))}</div>
  <div class="task-summary">{esc(task.get("summary"))}</div>
</div>
"""
    )
    done_col, delete_col = st.columns(2)
    with done_col:
        if st.button(f"Erledigt (+{xp_reward} XP)", key=f"done_{task_id}", use_container_width=True):
            complete_task(task_id, xp_reward)
            toast_success("Erledigt gespeichert.")
            time.sleep(0.3)
            rerun()
    with delete_col:
        if st.button("Löschen", key=f"delete_{task_id}", use_container_width=True):
            st.session_state.tasks = [item for item in st.session_state.tasks if item.get("id") != task_id]
            save_all_to_db()
            rerun()


if st.session_state.app_mode == "Dashboard":
    html_block(
        f"""
<div class="hero-band">
  <div>
    <h1 class="hero-title">Dein Alltags-Cockpit</h1>
    <p class="hero-copy">Plane, lerne, sammle XP und halte Tests, Hausaufgaben und Noten sauber zusammen.</p>
  </div>
  <div style="font-size:2.2rem;">{APP_ICON}</div>
</div>
"""
    )

    render_stats()
    render_calendar()

    with st.expander("KI-Lerncoach mit Text, Sprache und Bild", expanded=True):
        for message in st.session_state.messages[-8:]:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        reset_col, history_col = st.columns([1, 3])
        with reset_col:
            if st.button("Chat zurücksetzen", use_container_width=True):
                st.session_state.messages = [
                    {
                        "role": "assistant",
                        "content": f"Hi {st.session_state.user_id}! Ich habe den Chat zurückgesetzt.",
                    }
                ]
                save_all_to_db()
                rerun()
        with history_col:
            with st.popover("Chatverlauf ansehen" if hasattr(st, "popover") else "Chatverlauf"):
                for message in st.session_state.messages:
                    st.caption(f"{message['role']}: {message['content']}")

        with st.form("quick_chat_form", clear_on_submit=True):
            col_text, col_audio, col_image, col_send = st.columns([4, 2, 2, 1], vertical_alignment="center")
            with col_text:
                chat_text = st.text_input("Frag Kroko oder diktiere", key="chat_in", label_visibility="collapsed")
            with col_audio:
                chat_audio = voice_input("Diktieren", key="chat_aud", label_visibility="collapsed")
            with col_image:
                chat_image = st.file_uploader(
                    "Bild",
                    type=["jpg", "jpeg", "png", "heic"],
                    key="chat_img",
                    label_visibility="collapsed",
                )
            with col_send:
                submitted = st.form_submit_button("Senden", use_container_width=True)
            if submitted:
                final_text = chat_text.strip() if chat_text else ""
                if chat_audio:
                    transcript = transcribe_audio(chat_audio)
                    if transcript:
                        final_text = f"{final_text} {transcript}".strip()
                process_user_input(final_text, chat_image)

    with st.expander("Aufgabe schnell manuell anlegen"):
        with st.form("manual_task_form"):
            task_col_1, task_col_2, task_col_3 = st.columns(3)
            with task_col_1:
                manual_subject = st.selectbox("Fach", st.session_state.subjects)
                manual_type = st.selectbox("Typ", ["Hausaufgabe", "Test"])
            with task_col_2:
                manual_topic = st.text_input("Thema")
                manual_priority = st.selectbox("Priorität", ["🟡 Mittel", "🚨 Hoch"])
            with task_col_3:
                manual_date = st.date_input("Termin", value=today_date())
                manual_audio = voice_input("Thema einsprechen", key="aud_manual_task")
            if st.form_submit_button("Aufgabe speichern"):
                final_topic = manual_topic.strip()
                if manual_audio:
                    transcript = transcribe_audio(manual_audio)
                    if transcript:
                        final_topic = f"{final_topic} {transcript}".strip()
                if final_topic:
                    add_task(
                        {
                            "title": manual_subject,
                            "type": manual_type,
                            "summary": final_topic,
                            "prioritaet": manual_priority,
                            "termin": format_date(manual_date),
                        }
                    )
                    save_all_to_db()
                    rerun()
                else:
                    st.warning("Bitte ein Thema eingeben oder einsprechen.")

    st.markdown("### Workspace-Board")
    tests_col, homework_col = st.columns(2)

    with tests_col:
        st.markdown("<div class='section-title'>Tests & Arbeiten</div>", unsafe_allow_html=True)
        tests = [task for task in sorted_tasks(st.session_state.tasks) if task.get("type") == "Test"]
        if not tests:
            st.info("Keine offenen Tests.")
        for task in tests:
            render_task_card(task, xp_reward=20)

    with homework_col:
        st.markdown("<div class='section-title'>Hausaufgaben</div>", unsafe_allow_html=True)
        homework = [task for task in sorted_tasks(st.session_state.tasks) if task.get("type") == "Hausaufgabe"]
        if not homework:
            st.info("Keine offenen Hausaufgaben.")
        for task in homework:
            render_task_card(task, xp_reward=10)


# ============================================================================
# FLASHCARDS
# ============================================================================
elif st.session_state.app_mode == "Karteikarten":
    st.title("Intelligenter Karteikarten-Trainer")
    st.caption("Mit Leitner-Wiederholung: gewusste Karten wandern nach hinten, schwierige kommen schnell zurück.")

    today_text = format_date(today_date())
    due_cards = [
        card
        for card in st.session_state.flashcards
        if (parse_date(card.get("next_due")) or today_date()) <= today_date()
    ]
    learning_pool = due_cards or st.session_state.flashcards

    if learning_pool:
        idx = st.session_state.card_idx % len(learning_pool)
        card = learning_pool[idx]
        subject = card.get("subject", "Allgemein")
        prompt_text = card.get("answer") if st.session_state.card_flipped else card.get("question")
        label = "Antwort" if st.session_state.card_flipped else f"Frage · {subject}"
        box_class = "flashcard-box flipped" if st.session_state.card_flipped else "flashcard-box"

        html_block(
            f"""
<div class="{box_class}">
  <div class="flashcard-label">{esc(label)}</div>
  <div class="flashcard-text">{esc(prompt_text)}</div>
</div>
"""
        )
        st.caption(
            f"Box {card.get('box', 1)} · nächste Wiederholung: {card.get('next_due', today_text)} · "
            f"{len(due_cards)} Karte(n) heute fällig"
        )

        flip_col, known_col, unknown_col, delete_col = st.columns(4)
        with flip_col:
            if st.button("Umdrehen", use_container_width=True):
                st.session_state.card_flipped = not st.session_state.card_flipped
                rerun()
        with known_col:
            if st.button("Gewusst (+5 XP)", use_container_width=True):
                card["correct_count"] = int(card.get("correct_count", 0)) + 1
                card["box"] = min(int(card.get("box", 1)) + 1, max(LEITNER_INTERVALS))
                card["next_due"] = format_date(today_date() + timedelta(days=LEITNER_INTERVALS[card["box"]]))
                st.session_state.xp += 5
                bump_streak()
                st.session_state.card_idx += 1
                st.session_state.card_flipped = False
                save_all_to_db()
                rerun()
        with unknown_col:
            if st.button("Nochmal üben", use_container_width=True):
                card["box"] = 1
                card["next_due"] = today_text
                st.session_state.card_idx += 1
                st.session_state.card_flipped = False
                save_all_to_db()
                rerun()
        with delete_col:
            if st.button("Karte löschen", use_container_width=True):
                st.session_state.flashcards = [
                    item for item in st.session_state.flashcards if item.get("id") != card.get("id")
                ]
                st.session_state.card_flipped = False
                save_all_to_db()
                rerun()
    else:
        st.info("Dein Karteikasten ist leer. Erzeuge unten neue Karten oder lege manuell welche an.")

    st.divider()
    with st.expander("KI-Karten erstellen", expanded=False):
        with st.form("ki_card_generation_form"):
            ki_subject = st.selectbox("Fach", st.session_state.subjects, key="ki_card_sub")
            topic_text = st.text_input("Thema / Stoffgebiet", placeholder="z.B. Vokabeln Unidad 2")
            topic_audio = voice_input("Thema einsprechen", key="aud_card_generation")
            difficulty = st.select_slider(
                "Schwierigkeitsgrad",
                options=["Sehr Einfach", "Mittel", "Schwer / Knifflig"],
                value="Mittel",
            )
            count = st.number_input("Anzahl der Karten", min_value=1, max_value=12, value=5)

            if st.form_submit_button("KI-Karten erstellen"):
                final_topic = topic_text.strip() if topic_text else ""
                if topic_audio:
                    transcript = transcribe_audio(topic_audio)
                    if transcript:
                        final_topic = f"{final_topic} {transcript}".strip()

                if not final_topic:
                    st.warning("Bitte ein Thema eingeben oder einsprechen.")
                else:
                    prompt = f"""
Erstelle exakt {count} hochwertige Karteikarten für das Schulfach "{ki_subject}".
Thema: {final_topic}
Schwierigkeit: {difficulty}

Regeln:
- Jede Karte braucht eine konkrete Frage und eine lernbare Antwort.
- Keine leeren Felder.
- Antworte ausschließlich als valides JSON.

Schema:
{{"flashcards":[{{"subject":"{ki_subject}","question":"...","answer":"..."}}]}}
"""
                    result = ai_json_request([{"role": "user", "content": prompt}], temperature=0.45)
                    added = 0
                    for generated in (result or {}).get("flashcards", []):
                        if add_flashcard(generated):
                            added += 1
                    save_all_to_db()
                    st.success(f"{added} Karte(n) hinzugefügt.")
                    time.sleep(0.6)
                    rerun()

    with st.expander("Manuelle Lernkarte hinzufügen", expanded=False):
        with st.form("add_card_form"):
            subject = st.selectbox("Fach", st.session_state.subjects, key="manual_card_subject")
            question = st.text_input("Frage")
            question_audio = voice_input("Frage einsprechen", key="aud_manual_q")
            answer = st.text_input("Antwort")
            answer_audio = voice_input("Antwort einsprechen", key="aud_manual_a")
            if st.form_submit_button("Karte speichern"):
                final_question = question.strip() if question else ""
                final_answer = answer.strip() if answer else ""
                if question_audio:
                    transcript = transcribe_audio(question_audio)
                    if transcript:
                        final_question = f"{final_question} {transcript}".strip()
                if answer_audio:
                    transcript = transcribe_audio(answer_audio)
                    if transcript:
                        final_answer = f"{final_answer} {transcript}".strip()
                if add_flashcard({"subject": subject, "question": final_question, "answer": final_answer}):
                    save_all_to_db()
                    rerun()
                else:
                    st.warning("Frage und Antwort dürfen nicht leer sein.")


# ============================================================================
# GRADES
# ============================================================================
elif st.session_state.app_mode == "Notenspiegel":
    st.title("Persönlicher Notenspiegel")
    st.caption("Gewichtung nach österreichischem Schulalltag: Schularbeiten, Tests und Mitarbeit werden getrennt bewertet.")

    with st.form("grade_form"):
        grade_col_1, grade_col_2, grade_col_3 = st.columns(3)
        with grade_col_1:
            grade_subject = st.selectbox("Fach", st.session_state.subjects)
        with grade_col_2:
            grade_value = st.number_input("Note (1-5)", min_value=1.0, max_value=5.0, step=1.0)
        with grade_col_3:
            grade_type = st.selectbox("Leistungsart", GRADE_LABELS)
        grade_desc = st.text_input("Beschreibung", placeholder="z.B. Vokabeltest, Referat")
        grade_audio = voice_input("Beschreibung einsprechen", key="aud_grade_desc")

        if st.form_submit_button("Note eintragen"):
            final_desc = grade_desc.strip() if grade_desc else ""
            if grade_audio:
                transcript = transcribe_audio(grade_audio)
                if transcript:
                    final_desc = f"{final_desc} {transcript}".strip()
            add_grade(
                {
                    "subject": grade_subject,
                    "grade": grade_value,
                    "label": grade_type,
                    "desc": final_desc or grade_type,
                }
            )
            save_all_to_db()
            rerun()

    if not st.session_state.grades:
        st.info("Noch keine Noten eingetragen.")
    else:
        st.markdown("### Fachübersichten")
        for subject in st.session_state.subjects:
            subject_grades = [grade for grade in st.session_state.grades if grade.get("subject") == subject]
            if not subject_grades:
                continue
            average, details = calculate_subject_average(subject)
            st.markdown(f"#### {subject} · errechneter Stand: **{average:.2f}**")
            st.caption(details)
            for idx, grade in list(enumerate(st.session_state.grades)):
                if grade.get("subject") != subject:
                    continue
                grade_col, delete_col = st.columns([6, 1])
                with grade_col:
                    html_block(
                        f"<span class='grade-badge'>{int(grade.get('grade', 0))}</span>"
                        f"<b>{esc(grade.get('label'))}</b>: {esc(grade.get('desc'))} "
                        f"({esc(grade.get('date'))})"
                    )
                with delete_col:
                    if st.button("Löschen", key=f"del_g_{idx}", use_container_width=True):
                        st.session_state.grades.pop(idx)
                        save_all_to_db()
                        rerun()
            st.divider()


# ============================================================================
# LEARNING CENTER
# ============================================================================
elif st.session_state.app_mode == "Lernzentrum":
    html_block(
        """
<div class="gaming-shell">
  <h1 style="margin:0;font-size:1.65rem;">Kroko-Lernzentrum</h1>
  <p style="margin:.35rem 0 0 0;color:#cbd5e1;font-weight:600;">Fokusmodus für Zusammenfassungen, Handschrift, Fehlertraining und Quests.</p>
</div>
"""
    )

    st.subheader("KI-Stoff-Zusammenfasser")
    with st.expander("Text, Datei oder Sprachnachricht zusammenfassen", expanded=True):
        summary_text = st.text_area("Lernstoff einfügen", height=150)
        summary_audio = voice_input("Stoff einsprechen", key="aud_summary_engine")
        summary_file = st.file_uploader("Textdatei hochladen", type=["txt"])

        if st.button("Stoff zusammenfassen", use_container_width=True):
            final_source = summary_text.strip() if summary_text else ""
            if summary_file:
                final_source += "\n" + summary_file.read().decode("utf-8", errors="ignore")
            if summary_audio:
                transcript = transcribe_audio(summary_audio)
                if transcript:
                    final_source += "\n" + transcript

            if not final_source.strip():
                st.warning("Bitte Text eingeben, Datei hochladen oder Sprache aufnehmen.")
            else:
                prompt = f"""
Fasse den folgenden Lernstoff lernfertig zusammen.
Struktur:
1. Kurzübersicht
2. Kernbegriffe
3. Wichtigste Zusammenhänge
4. Mini-Lernplan für 20 Minuten
5. 5 Kontrollfragen mit Antworten

Stoff:
{final_source}
"""
                result = ai_text_request(prompt, temperature=0.25)
                if result:
                    st.session_state.active_summary = result
                    save_all_to_db()

        if st.session_state.active_summary:
            st.markdown("#### Deine Zusammenfassung")
            st.info(st.session_state.active_summary)

    st.divider()
    st.subheader("Musterschrift-Gedächtnis")
    with st.expander("Persönliches Handschriftprofil lernen", expanded=False):
        st.info(
            "Schreibe diesen Satz auf ein Blatt und lade ein Foto hoch: "
            "„Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. Kroko lernt 12345!“"
        )
        sample_img = st.file_uploader(
            "Foto deiner Handschriftprobe",
            type=["jpg", "jpeg", "png", "heic"],
            key="handwriting_sample",
        )
        if st.button("Schriftprobe analysieren", use_container_width=True) and sample_img:
            img_b64 = encode_image(sample_img)
            if img_b64:
                result = None
                if client:
                    try:
                        response = client.chat.completions.create(
                            model=OPENAI_MODEL,
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": (
                                                "Analysiere Schreibstil, Neigung, Buchstabenabstände, "
                                                "Ziffern, typische Verwechslungen und Entzifferungshinweise. "
                                                "Formuliere ein kompaktes Profil für zukünftige Bildauswertung."
                                            ),
                                        },
                                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                                    ],
                                }
                            ],
                        )
                        result = response.choices[0].message.content.strip()
                    except Exception as exc:
                        st.error(f"Analyse fehlgeschlagen: {exc}")
                else:
                    st.warning("OpenAI ist noch nicht konfiguriert.")
                if result:
                    st.session_state.handwriting_analysis = result
                    save_all_to_db()
                    rerun()
        if st.session_state.handwriting_analysis:
            st.success("Aktives Handschriftprofil")
            st.info(st.session_state.handwriting_analysis)

    st.divider()
    st.subheader("Aktive Kuckuckseier")
    if st.session_state.kuckuckseier:
        for idx, egg in list(enumerate(st.session_state.kuckuckseier)):
            html_block(
                f"""
<div class="error-box">
  <b>Kuckucksei #{idx + 1}</b><br>
  <b>Fach:</b> {esc(egg.get("subject"))}<br>
  <b>Fehler:</b> {esc(egg.get("error_found"))}<br>
  <b>Challenge:</b> {esc(egg.get("training_task"))}
</div>
"""
            )
            with st.form(f"solve_egg_form_{idx}"):
                answer_text = st.text_area("Deine Antwort", key=f"egg_ans_txt_{idx}")
                answer_audio = voice_input("Oder Lösung einsprechen", key=f"egg_ans_aud_{idx}")
                if st.form_submit_button("Lösung einreichen"):
                    final_answer = answer_text.strip() if answer_text else ""
                    if answer_audio:
                        transcript = transcribe_audio(answer_audio)
                        if transcript:
                            final_answer = f"{final_answer} {transcript}".strip()
                    if not final_answer:
                        st.warning("Bitte eine Antwort eingeben oder einsprechen.")
                    else:
                        prompt = f"""
Bewerte die Schülerantwort als JSON.
Aufgabe: {egg.get("training_task")}
Antwort: {final_answer}

Schema:
{{"correct": true, "feedback": "kurzes, hilfreiches Feedback"}}
"""
                        result = ai_json_request([{"role": "user", "content": prompt}], temperature=0.0)
                        if result and result.get("correct") is True:
                            st.success("Gefixt. +30 XP")
                            st.session_state.xp += 30
                            bump_streak()
                            st.session_state.kuckuckseier.pop(idx)
                            save_all_to_db()
                            time.sleep(0.6)
                            rerun()
                        elif result:
                            st.error(result.get("feedback", "Noch nicht ganz. Versuch es erneut."))
    else:
        st.info("Keine ungelösten Kuckuckseier.")

    with st.expander("Korrigierte Arbeiten einsenden", expanded=False):
        corrected_uploads = st.file_uploader(
            "Bilder hochladen",
            type=["jpg", "jpeg", "png", "heic"],
            accept_multiple_files=True,
            key="corrected_uploads",
        )
        corrected_subject = st.selectbox("Fach", st.session_state.subjects, key="corr_sub_box")
        if st.button("Scans starten", use_container_width=True) and corrected_uploads:
            profile_text = st.session_state.get("handwriting_analysis") or "Normale Schülerschrift"
            for file in corrected_uploads[:4]:
                img_b64 = encode_image(file)
                if not img_b64:
                    continue
                scan_prompt = f"""
Finde einen konkreten Lernfehler in dieser korrigierten Arbeit.
Fach: {corrected_subject}
Handschriftprofil: {profile_text}

Antworte exakt als JSON:
{{"error_found": "konkreter Fehler", "training_task": "passende Mini-Übungsaufgabe"}}
"""
                result = ai_json_request(
                    [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": scan_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                            ],
                        }
                    ],
                    temperature=0.1,
                )
                if result and result.get("error_found") and result.get("training_task"):
                    st.session_state.kuckuckseier.append(
                        {
                            "subject": corrected_subject,
                            "error_found": result.get("error_found"),
                            "training_task": result.get("training_task"),
                        }
                    )
            save_all_to_db()
            rerun()

    st.divider()
    st.subheader("Active Quest-Reihe")
    quests_blocked = len(st.session_state.kuckuckseier) > 0

    if not st.session_state.gaming_quests:
        with st.form("quest_gen_form"):
            quest_subject = st.selectbox("Fach", st.session_state.subjects, key="quest_subject")
            quest_topic = st.text_input("Thema")
            quest_audio = voice_input("Thema einsprechen", key="aud_quest_topic")
            if st.form_submit_button("Quest-Reihe schmieden"):
                final_topic = quest_topic.strip() if quest_topic else ""
                if quest_audio:
                    transcript = transcribe_audio(quest_audio)
                    if transcript:
                        final_topic = f"{final_topic} {transcript}".strip()
                if not final_topic:
                    st.warning("Bitte ein Thema eingeben oder einsprechen.")
                else:
                    prompt = f"""
Baue drei kurze, aufeinander aufbauende Lernquests.
Fach: {quest_subject}
Thema: {final_topic}

Schema:
{{"quests":[{{"step":1,"title":"...","description":"konkrete Aufgabe"}}]}}
"""
                    result = ai_json_request([{"role": "user", "content": prompt}], temperature=0.35)
                    st.session_state.gaming_quests = (result or {}).get("quests", [])
                    save_all_to_db()
                    rerun()
    else:
        if quests_blocked:
            st.warning("Quests sind pausiert, bis die Kuckuckseier gelöst sind.")
        for idx, quest in list(enumerate(st.session_state.gaming_quests)):
            quest_class = "locked" if quests_blocked else "active" if idx == 0 else ""
            html_block(
                f"""
<div class="quest-card {quest_class}">
  <b>Quest {esc(quest.get("step", idx + 1))}: {esc(quest.get("title"))}</b>
  <p>{esc(quest.get("description"))}</p>
</div>
"""
            )
            if idx == 0 and not quests_blocked:
                if st.button("Quest abschließen (+25 XP)", use_container_width=True):
                    st.session_state.gaming_quests.pop(0)
                    st.session_state.xp += 25
                    bump_streak()
                    save_all_to_db()
                    st.balloons()
                    rerun()

