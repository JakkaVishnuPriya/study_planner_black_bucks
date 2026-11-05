# Smart Study Planner Agent using LangGraph

An AI-assisted study planner built with **Python, LangGraph, OpenAI API, Streamlit and SQLite**.

## Features

- Add subjects, difficulty, exam dates and syllabus topics.
- Generate a multi-day personalized study plan.
- Display today's and tomorrow's study lists.
- Mark sessions complete and track syllabus progress.
- View subject-wise completion and weekly progress.
- Revise the future schedule using pending topics.
- Daily motivational quote.
- LangGraph workflow with state, nodes, edges and conditional routing.
- SQLite storage for subjects, topics, study sessions and settings.
- Built-in fallback scheduler if the OpenAI API is unavailable.

## Project structure

```text
Smart_Study_Planner/
├── app.py
├── agents/
│   └── planner.py
├── graph/
│   ├── state.py
│   └── workflow.py
├── database/
│   └── db.py
├── .streamlit/
│   └── config.toml
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Deploy directly to Streamlit Community Cloud

You do not need to run the application locally.

1. Extract this ZIP file.
2. Create a new **public or private GitHub repository**.
3. Upload all extracted project files and folders to the repository root. Make sure `app.py` is at the root.
4. Open https://share.streamlit.io/ and sign in with GitHub.
5. Select **Create app**.
6. Choose your repository, branch (usually `main`) and main file path `app.py`.
7. Open the app's **Advanced settings / Secrets** before or after deployment.
8. Add the following TOML secrets:

```toml
OPENAI_API_KEY = "your_real_openai_api_key"
OPENAI_MODEL = "gpt-4o-mini"
```

9. Save and deploy. Streamlit will install dependencies from `requirements.txt`.

**Important:** Do not upload your real `.env` file or API key to GitHub. `.env` is ignored by `.gitignore`. On Streamlit Community Cloud, use the app's Secrets settings as shown above. The application reads the key from Streamlit secrets automatically.

## Optional local configuration

For local development only:

1. Copy `.env.example` to `.env`.
2. Add your real API key.
3. Install dependencies with `pip install -r requirements.txt`.
4. Run `streamlit run app.py`.

The user requested direct deployment, so local execution is not required.

## First-time use

1. Open **Subjects & Topics**.
2. Add a subject, difficulty, exam date and topics (one topic per line).
3. Set daily available study hours and preferred start time in the sidebar.
4. Click **Generate / regenerate study plan**.
5. Open **Dashboard** to see today's and tomorrow's tasks.
6. Mark topics complete as you study.
7. Open **Progress & Reports** to see completion.
8. Use **Revise my future schedule** to reschedule incomplete topics.

## How the AI workflow works

- `priority_analysis`: reviews subject difficulty, exam date and pending topics.
- `generate_plan`: requests a structured schedule from the OpenAI API.
- `evaluate_progress`: checks whether topics remain pending.
- `revise_schedule`: creates a revised plan for outstanding topics.
- LangGraph manages state and conditional routing between these nodes.

Some operations such as saving records and calculating progress are deterministic Python/SQLite operations rather than separate LLM agents. This keeps the application more reliable and reduces API calls.

## Storage note for Streamlit Community Cloud

This starter project uses a local SQLite database file. It is suitable for a prototype/demo and stores data while the deployed app's filesystem is retained. Streamlit Community Cloud's local filesystem is not guaranteed to be permanent across app restarts, rebuilds or redeployments. For durable multi-user production storage, migrate the database to a hosted service such as PostgreSQL or Supabase before relying on it for long-term records.

## API cost and model

The project uses the OpenAI API only when generating or revising a plan. API usage is billed separately from a ChatGPT subscription. The built-in fallback scheduler can still create a basic plan if no key is configured or an API request fails.

You can change the model by editing `OPENAI_MODEL` in Streamlit secrets.
