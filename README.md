# SQL Assistant (NL2SQLBot)

## Overview

SQL Assistant is an intelligent chatbot that lets you query SQL Server databases using plain English — no SQL knowledge required. Ask a question in natural language, and the app generates the correct SQL query, executes it, and returns easy-to-understand results, complete with automatic charts.

---

## Workflow

<img width="744" height="492" alt="NL2SQLBot: Democratizing Data Access with AI-Powered Natural Language to SQL" src="https://github.com/user-attachments/assets/06d00b07-5d25-4f6c-bcc1-465f204ec804" />

*Figure not finalized.*

This application follows a multi-stage pipeline to turn a natural language question into a SQL query, executed results, and visualizations.

### 1. Initialization Phase

- App starts in the `__main__` block
- Loads available LLM models from Ollama (`get_available_models()`)
- Loads previous chat history from `chat_history.json`
- Builds the Gradio UI (`create_interface()`)

### 2. Connection Setup Phase

**User actions:**
- Selects a connection method (connection string or individual fields)
- Enters SQL Server details (server name, authentication type)
- Clicks **Test Connection**

**Behind the scenes:**
- `test_connection()` validates credentials and stores `SERVER_NAME` / `CURRENT_AUTH_TYPE`
- `get_available_databases()` queries SQL Server for all databases and returns the list

### 3. Database Connection Phase

**User actions:**
- Selects a database from the dropdown
- Clicks **Connect Database**

**Behind the scenes**, `connect_to_database()` runs three optimized steps:
1. **Schema caching** — `load_schema_with_validation()` checks whether the cached schema is still valid (table count, last-modified date, cache age)
2. **Schema extraction** — if the cache is invalid, `get_database_schema()` extracts a fresh schema (tables, columns, relationships) directly from SQL Server's system tables
3. **Vector DB creation** — `create_or_load_vector_db()` embeds the schema into a ChromaDB vector store for semantic search

### 4. Few-Shot Examples Upload

**User actions:**
- Uploads a JSON file of example question → SQL pairs

**Behind the scenes:**
- `upload_few_shot_examples()` validates and stores the examples in the `FEW_SHOT_EXAMPLES` global
- These examples guide the LLM's SQL style and pattern-matching

### 5. Model Selection Phase

**User actions:**
- Selects an LLM from the dropdown
- Clicks **Connect Model**

**Behind the scenes:**
- `connect_model()` stores `LLM_MODEL` globally and validates the connection to the local Ollama service

### 6. Query Execution Phase (Core Workflow)

When the user submits a question, it flows through this pipeline:

```
User Question
    │
    ▼
find_relevant_tables()
    → Vector DB semantic search for related tables (top 5)
    │
    ▼
build_enhanced_sql_prompt()
    → Combines retrieved schema + matched few-shot examples + rules
    │
    ▼
query_llm_with_reasoning()
    → Sends the prompt to the Ollama LLM
    │
    ▼
extract_sql_and_reasoning()
    → Parses the LLM response into a SQL query + reasoning
    │
    ▼
validate_and_sanitize_sql()
    → Uses SQLGlot to verify valid T-SQL syntax
    → Blocks dangerous commands (DROP, DELETE, INSERT, UPDATE, ALTER, etc.)
    │
    ▼
execute_safe_query()
    → Runs the SQL against the database via SQLAlchemy
    → Returns results as a DataFrame
    │
    ▼
convert_sql_results_to_nlp()
    → Uses the LLM to summarize results in natural language
    │
    ▼
generate_plotly_visualizations()
    → Classifies DataFrame columns (numeric, categorical, datetime)
    → Builds up to 29 candidate chart types (bar, pie, scatter, heatmap,
      gauge, waterfall, treemap, sunburst, etc.)
    → Scores each candidate on 5 criteria (data utilization, variety,
      relevance, complexity, uniqueness)
    → Returns the top 4 scored visualizations
    │
    ▼
add_to_history()
    → Saves the query, response, reasoning, and SQL to chat history
```

### 7. History & Regeneration

**User actions:**
- Selects a previous query from history
- Optionally regenerates its visualizations

**Behind the scenes:**
- `update_history_dropdown()` lists all past queries for the current database
- `regenerate_visuals_from_history()` re-executes the stored SQL and rebuilds fresh charts

---

## Key Global State Variables

| Variable | Purpose |
|---|---|
| `SERVER_NAME` | Current SQL Server |
| `CURRENT_DB` | Connected database |
| `CURRENT_DB_ENGINE` | SQLAlchemy connection |
| `LLM_MODEL` | Selected LLM model |
| `SCHEMA_INFO` | Database schema details |
| `VECTOR_DB` | Chroma vector store for semantic search |
| `FEW_SHOT_EXAMPLES` | User-provided query examples |
| `CHAT_HISTORY` | All previous interactions |

---

## Optimization Strategy

- **Schema caching** — avoids expensive re-extraction when the database hasn't changed
- **Vector DB caching** — only recreates embeddings when the schema changes
- **Semantic search** — uses the vector DB to find relevant tables faster and more accurately than plain keyword matching

This creates a complete pipeline: natural language → SQL → results → visualizations.

---

## Prerequisites (must do before using)

### 1. SQL Server ODBC Driver
Required for database connectivity.
- Download: https://go.microsoft.com/fwlink/?linkid=2249006
- Run the installer
- Choose "Download" then "Install" when prompted

### 2. Ollama (AI Engine)
Required for natural language understanding.
1. Download & install from https://ollama.ai/download
2. Run Ollama (it should appear in your system tray)
3. Pull a model from the Command Prompt (cloud models tend to respond faster):
   ```bash
   ollama pull gpt-oss:20b-cloud
   ```

### 3. Database Access
You'll need:
- SQL Server name/instance
- Database name(s) you want to query
- An authentication type:
  - Windows Authentication (recommended)
  - SQL Server Authentication (username/password)
  - Connection string

---

## Preparing Effective Few-Shot Examples

**Golden rules for good examples:**
1. **Be specific** — match your actual database structure
2. **Cover common questions** — include examples for frequent query patterns
3. **Show variety** — different question styles, different SQL patterns

---

## Pro Tips for Best Results

**Writing questions:**
- Be specific — "sales in Q3 2024," not "show me sales"
- Include context — "products sold in New York stores"
- Use natural language — "who are our top 10 customers by purchase amount"

**Database connection:**
- Start with Windows Authentication if available
- Test the connection against the `master` database first
- Use `TrustServerCertificate=True` for local development

**AI model selection:**
- Local models: `llama3.2:1b` or `sqlcoder:15b`
- Cloud models (smaller, faster): `deepseek-v3.1:671b-cloud`

> **Note:** Cloud models send prompts to external servers — check your data security policies before using them.

---

## Troubleshooting

**Quick fixes:**
- Restart everything — close the app, stop Ollama, restart both
- Check logs — review the Command Prompt window for error messages
- Reinstall — run `install.bat` again with a fresh download

---

## File Structure

After installation:

```
SQL_Assistant/
├── venv/                    # Python virtual environment
├── schema_cache_*.json      # Cached database schemas
├── vector_db_*/             # Vector database stores
├── chat_history.json        # Your query history
├── few_shot_examples.json   # Your training examples
├── app.py                   # Main application
├── install.bat              # Setup script
└── start.bat                # Launcher script
```

---

## Support & Resources

**For help:**
1. Check error messages in the Command Prompt window
2. Review the installation checklist above
3. Ensure all prerequisites are installed

**Need better examples?**
- Start with a good number of examples for better results
- Add more as you discover common query patterns
- Update your JSON file anytime

**Performance issues?**
- Try a smaller AI model
- Close other applications
- Use cloud models for faster queries
