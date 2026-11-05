import json
import os
from datetime import datetime, timedelta
from openai import OpenAI

def _api_key():
    import streamlit as st

    key = st.secrets.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError("OPENAI_API_KEY is missing in Streamlit Secrets.")

    return str(key).strip()

def _model():
    import streamlit as st
    return st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")

def call_json_llm(system_prompt, user_prompt):
    key = _api_key()
    if not key:
        return None
    client = OpenAI(api_key=key)
    response = client.chat.completions.create(
        model=_model(),
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)

def deterministic_plan(subjects, daily_hours, start_time, planning_days, today):
    """Fallback scheduler used if the API is unavailable."""
    tasks = []
    for subject in subjects:
        for topic in subject.get("topics", []):
            if isinstance(topic, dict):
                if topic.get("status") == "completed":
                    continue
                title = topic["title"]
            else:
                title = topic
            tasks.append({
                "subject": subject["name"], "topic": title,
                "difficulty": subject.get("difficulty", "Medium"),
                "exam_date": subject.get("exam_date", today),
            })
    # Prioritize nearest exam, then harder subjects.
    difficulty_order = {"Hard": 0, "Medium": 1, "Easy": 2}
    tasks.sort(key=lambda x: (x["exam_date"], difficulty_order.get(x["difficulty"], 1)))
    hours_per_day = max(1, int(daily_hours))
    max_minutes = hours_per_day * 60
    cursor = datetime.strptime(start_time, "%H:%M")
    sessions = []
    day_index = 0
    used_minutes = 0
    for task in tasks:
        if day_index >= planning_days:
            break
        duration = 60 if task["difficulty"] == "Hard" else 45
        if used_minutes + duration > max_minutes:
            day_index += 1
            used_minutes = 0
            cursor = datetime.strptime(start_time, "%H:%M")
        if day_index >= planning_days:
            break
        day = datetime.strptime(today, "%Y-%m-%d").date() + timedelta(days=day_index)
        sessions.append({
            "date": day.isoformat(),
            "subject": task["subject"],
            "topic": task["topic"],
            "start_time": cursor.strftime("%H:%M"),
            "duration_minutes": duration,
            "notes": "Prioritized by exam date and subject difficulty.",
        })
        cursor += timedelta(minutes=duration + 10)
        used_minutes += duration
    return sessions

def generate_plan(subjects, daily_hours, start_time, planning_days, today, revision=False):
    system_prompt = (
        "You are a practical academic study-planning assistant. "
        "Return valid JSON only. Never schedule a topic marked completed. "
        "Respect the student's daily available study hours. Avoid overlapping sessions. "
        "Schedule each pending topic at most once. Prioritize nearer exams and harder subjects. "
        "Include short notes explaining the session."
    )
    user_prompt = f"""
Create a {planning_days}-day study schedule starting on {today}.
Available study time per day: {daily_hours} hours.
Preferred start time: {start_time}.
Revision mode: {revision}.
Subjects and topics (JSON):
{json.dumps(subjects, ensure_ascii=False)}

Return exactly this JSON structure:
{{
  "sessions": [
    {{
      "date": "YYYY-MM-DD",
      "subject": "subject name",
      "topic": "topic name",
      "start_time": "HH:MM",
      "duration_minutes": 45,
      "notes": "short practical note"
    }}
  ],
  "message": "short explanation"
}}
Schedule only the supplied incomplete topics. Use dates within the requested planning window.
"""
    try:
        result = call_json_llm(system_prompt, user_prompt)
        if result and isinstance(result.get("sessions"), list):
            sessions = _validate_sessions(
                result["sessions"], subjects, today, planning_days, daily_hours
            )
            if sessions:
                return sessions, result.get("message", "Plan generated using the LLM.")
    except Exception:
        pass
    sessions = deterministic_plan(subjects, daily_hours, start_time, planning_days, today)
    return sessions, "Plan generated using the built-in fallback scheduler. Check your API key to enable AI-generated planning."

def _validate_sessions(raw_sessions, subjects, today, planning_days, daily_hours):
    allowed = {}
    for subject in subjects:
        allowed[subject["name"]] = set(
            t["title"] if isinstance(t, dict) else t
            for t in subject.get("topics", [])
            if not isinstance(t, dict) or t.get("status") != "completed"
        )
    start = datetime.strptime(today, "%Y-%m-%d").date()
    end = start + timedelta(days=planning_days - 1)
    daily_totals = {}
    clean = []
    for item in raw_sessions:
        try:
            subject = str(item["subject"])
            topic = str(item["topic"])
            day = datetime.strptime(str(item["date"]), "%Y-%m-%d").date()
            start_time = datetime.strptime(str(item["start_time"]), "%H:%M").strftime("%H:%M")
            duration = max(20, min(120, int(item.get("duration_minutes", 45))))
            if subject not in allowed or topic not in allowed[subject]:
                continue
            if day < start or day > end:
                continue
            daily_totals[day.isoformat()] = daily_totals.get(day.isoformat(), 0) + duration
            if daily_totals[day.isoformat()] > daily_hours * 60:
                continue
            clean.append({
                "date": day.isoformat(), "subject": subject, "topic": topic,
                "start_time": start_time, "duration_minutes": duration,
                "notes": str(item.get("notes", ""))[:240],
            })
            allowed[subject].discard(topic)
        except Exception:
            continue
    return clean
