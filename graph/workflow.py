from langgraph.graph import StateGraph, START, END
from graph.state import StudyPlannerState
from agents.planner import generate_plan

def priority_analysis_node(state: StudyPlannerState):
    subjects = state.get("subjects", [])
    ranking = []
    for subject in subjects:
        total = len(subject.get("topics", []))
        pending = sum(
            1 for topic in subject.get("topics", [])
            if not isinstance(topic, dict) or topic.get("status") != "completed"
        )
        ranking.append(
            f"{subject.get('name')} ({subject.get('difficulty')}, "
            f"exam {subject.get('exam_date')}, {pending}/{total} pending)"
        )
    return {"priority_summary": "; ".join(ranking)}

def generate_plan_node(state: StudyPlannerState):
    sessions, message = generate_plan(
        subjects=state.get("subjects", []),
        daily_hours=state.get("daily_hours", 3),
        start_time=state.get("start_time", "17:00"),
        planning_days=state.get("planning_days", 7),
        today=state.get("today"),
        revision=False,
    )
    return {"sessions": sessions, "message": message}

def evaluate_progress_node(state: StudyPlannerState):
    pending = state.get("pending_topics", [])
    return {"needs_revision": len(pending) > 0}

def revise_schedule_node(state: StudyPlannerState):
    # Build a planner-friendly subject structure from the outstanding topic list.
    grouped = {}
    for item in state.get("pending_topics", []):
        name = item["subject"]
        grouped.setdefault(name, {
            "name": name,
            "difficulty": item.get("difficulty", "Medium"),
            "exam_date": item.get("exam_date", state.get("today")),
            "topics": [],
        })
        grouped[name]["topics"].append({"title": item["topic"], "status": "pending"})
    sessions, message = generate_plan(
        subjects=list(grouped.values()),
        daily_hours=state.get("daily_hours", 3),
        start_time=state.get("start_time", "17:00"),
        planning_days=state.get("planning_days", 7),
        today=state.get("today"),
        revision=True,
    )
    return {"sessions": sessions, "message": message}

def route_action(state: StudyPlannerState):
    return "plan" if state.get("action") == "plan" else "revise"

def route_revision(state: StudyPlannerState):
    return "revise" if state.get("needs_revision") else "finish"

def build_graph():
    graph = StateGraph(StudyPlannerState)
    graph.add_node("priority_analysis", priority_analysis_node)
    graph.add_node("generate_plan", generate_plan_node)
    graph.add_node("evaluate_progress", evaluate_progress_node)
    graph.add_node("revise_schedule", revise_schedule_node)

    graph.add_conditional_edges(
        START, route_action,
        {"plan": "priority_analysis", "revise": "evaluate_progress"},
    )
    graph.add_edge("priority_analysis", "generate_plan")
    graph.add_edge("generate_plan", END)

    graph.add_conditional_edges(
        "evaluate_progress", route_revision,
        {"revise": "revise_schedule", "finish": END},
    )
    graph.add_edge("revise_schedule", END)
    return graph.compile()

def run_workflow(**kwargs):
    app = build_graph()
    return app.invoke(kwargs)
