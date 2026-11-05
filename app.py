from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

from database.db import (
    init_db, add_subject, list_subjects, delete_subject, get_settings,
    save_settings, get_sessions, update_session_status, get_progress_summary,
    clear_future_plan, save_sessions, get_pending_topics, get_subjects_for_planner,
)
from graph.workflow import run_workflow

TZ = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(TZ).date()

st.set_page_config(
    page_title="Smart Study Planner",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

QUOTES = [
    "Small progress every day leads to big results.",
    "Discipline is choosing what you want most over what you want now.",
    "Don't study just to finish. Study to understand.",
    "Your future is created by what you do today.",
    "Consistency turns small efforts into remarkable results.",
    "A little progress each day adds up to big results.",
    "Focus on progress, not perfection.",
]

def show_session(session):
    cols = st.columns([1.2, 2.2, 1.3, 1.2, 1.4])
    cols[0].write(session["start_time"])
    cols[1].write(f"**{session['subject']}**  \n{session['topic']}")
    cols[2].write(f"{session['duration_minutes']} min")
    status = session["status"]
    cols[3].write("✅ Done" if status == "completed" else ("⏭️ Skipped" if status == "skipped" else "🕒 Pending"))
    if status != "completed":
        if cols[4].button("Mark done", key=f"done_{session['id']}"):
            update_session_status(session["id"], "completed")
            st.rerun()
    else:
        if cols[4].button("Undo", key=f"undo_{session['id']}"):
            update_session_status(session["id"], "pending")
            st.rerun()

st.title("📚 Smart Study Planner")
st.caption("Your AI-powered study coach — plan, track, and adapt.")

settings = get_settings()
subjects = list_subjects()
progress = get_progress_summary()

quote_index = TODAY.toordinal() % len(QUOTES)
st.info(f"✨ **Today's motivation:** {QUOTES[quote_index]}")

with st.sidebar:
    st.header("⚙️ Planner settings")
    daily_hours = st.number_input(
        "Available study hours per day",
        min_value=1, max_value=16, value=int(settings["daily_hours"]), step=1,
    )
    start_time = st.time_input(
        "Preferred study start time",
        value=datetime.strptime(settings["start_time"], "%H:%M").time(),
    )
    planning_days = st.slider("Plan duration (days)", 3, 14, int(settings["planning_days"]))
    if st.button("Save settings", use_container_width=True):
        save_settings(int(daily_hours), start_time.strftime("%H:%M"), int(planning_days))
        st.success("Settings saved.")

tab_dashboard, tab_setup, tab_reports = st.tabs(
    ["🏠 Dashboard", "➕ Subjects & Topics", "📈 Progress & Reports"]
)

with tab_setup:
    st.subheader("Add a subject")
    with st.form("add_subject_form", clear_on_submit=True):
        subject_name = st.text_input("Subject name", placeholder="e.g. Machine Learning")
        difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
        exam_date = st.date_input("Exam date", value=TODAY + timedelta(days=30), min_value=TODAY)
        topic_text = st.text_area(
            "Topics (one topic per line)",
            placeholder="Introduction to ML\nRegression\nClassification\nClustering",
            height=130,
        )
        submitted = st.form_submit_button("Add subject", use_container_width=True)
        if submitted:
            topics = [line.strip() for line in topic_text.splitlines() if line.strip()]
            if not subject_name.strip():
                st.error("Enter a subject name.")
            elif not topics:
                st.error("Add at least one topic, one per line.")
            else:
                add_subject(subject_name.strip(), difficulty, exam_date.isoformat(), topics)
                st.success(f"Added {subject_name} with {len(topics)} topics.")
                st.rerun()

    st.divider()
    st.subheader("Your subjects")
    subjects = list_subjects()
    if not subjects:
        st.info("No subjects yet. Add your first subject above.")
    else:
        for subject in subjects:
            with st.expander(f"{subject['name']} · {subject['difficulty']} · Exam: {subject['exam_date']}"):
                st.write(f"Topics: {', '.join(subject['topics'])}")
                st.caption(f"{subject['completed_topics']} of {subject['total_topics']} topics completed")
                if st.button("Delete subject", key=f"delete_subject_{subject['id']}"):
                    delete_subject(subject["id"])
                    st.warning("Subject deleted.")
                    st.rerun()

    st.divider()
    st.subheader("Generate your study plan")
    st.write("Add your subjects and topics first. The planner will create a schedule for the selected number of days.")
    if st.button("✨ Generate / regenerate study plan", type="primary", use_container_width=True):
        planner_subjects = get_subjects_for_planner()
        if not planner_subjects:
            st.error("Add at least one subject with topics before generating a plan.")
        else:
            with st.spinner("Analysing priorities and generating your study plan..."):
                clear_future_plan(TODAY.isoformat())
                result = run_workflow(
                    action="plan",
                    subjects=planner_subjects,
                    daily_hours=int(daily_hours),
                    start_time=start_time.strftime("%H:%M"),
                    planning_days=int(planning_days),
                    today=TODAY.isoformat(),
                )
                save_sessions(result.get("sessions", []))
            st.success(f"Your {planning_days}-day study plan is ready!")
            if result.get("message"):
                st.caption(result["message"])
            st.rerun()

with tab_dashboard:
    subjects = list_subjects()
    sessions_today = get_sessions(TODAY.isoformat())
    tomorrow = TODAY + timedelta(days=1)
    sessions_tomorrow = get_sessions(tomorrow.isoformat())
    progress = get_progress_summary()

    st.subheader(f"Welcome back! · {TODAY.strftime('%A, %d %B %Y')}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Topics completed", progress["completed"], delta=f"{progress['completion_pct']}% overall")
    m2.metric("Topics pending", progress["pending"])
    m3.metric("Study sessions", progress["total_sessions"])
    m4.metric("Subjects", len(subjects))

    st.progress(progress["completion_pct"] / 100 if progress["total_topics"] else 0)
    st.caption(f"Overall syllabus completion: {progress['completed']} / {progress['total_topics']} topics")

    left, right = st.columns(2)
    with left:
        st.markdown("### ☀️ Today's list")
        if not sessions_today:
            st.info("No study sessions planned for today. Add subjects and generate a plan.")
        else:
            for session in sessions_today:
                show_session(session)
    with right:
        st.markdown(f"### 🌤️ Tomorrow's list · {tomorrow.strftime('%d %b')}")
        if not sessions_tomorrow:
            st.info("No sessions scheduled for tomorrow yet.")
        else:
            for session in sessions_tomorrow:
                show_session(session)

    st.divider()
    st.subheader("Adaptive study coach")
    st.write("If you missed sessions or have pending topics, ask the planner to rebuild the remaining schedule.")
    if st.button("🔄 Revise my future schedule", use_container_width=True):
        pending = get_pending_topics()
        if not pending:
            st.success("Great! There are no pending topics to reschedule.")
        else:
            with st.spinner("Reviewing pending topics and revising your schedule..."):
                result = run_workflow(
                    action="revise",
                    subjects=get_subjects_for_planner(),
                    pending_topics=pending,
                    daily_hours=int(daily_hours),
                    start_time=start_time.strftime("%H:%M"),
                    planning_days=int(planning_days),
                    today=TODAY.isoformat(),
                )
                clear_future_plan(TODAY.isoformat(), keep_completed=True)
                save_sessions(result.get("sessions", []))
            st.success("Your future schedule has been revised.")
            st.rerun()

with tab_reports:
    st.subheader("Your learning progress")
    progress = get_progress_summary()
    a, b, c = st.columns(3)
    a.metric("Completed", progress["completed"])
    b.metric("Pending", progress["pending"])
    c.metric("Completion", f"{progress['completion_pct']}%")
    if progress["subject_progress"]:
        st.markdown("### Subject-wise progress")
        for item in progress["subject_progress"]:
            st.write(f"**{item['name']}** — {item['completed']}/{item['total']} topics")
            st.progress(item["completed"] / item["total"] if item["total"] else 0)
    else:
        st.info("Add subjects and topics to see your progress.")
    st.markdown("### Weekly study sessions")
    week_sessions = []
    for offset in range(7):
        day = TODAY + timedelta(days=offset)
        day_sessions = get_sessions(day.isoformat())
        week_sessions.append((day, day_sessions))
    for day, day_sessions in week_sessions:
        done = sum(1 for x in day_sessions if x["status"] == "completed")
        st.write(f"**{day.strftime('%A, %d %b')}** — {done}/{len(day_sessions)} sessions completed")
        if day_sessions:
            st.caption(" · ".join(f"{x['subject']}: {x['topic']}" for x in day_sessions))
