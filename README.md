## Overview

SQL Assistant is an intelligent chatbot that allows you to query your SQL Server databases using plain English. No SQL knowledge required! Simply ask questions in natural language, and the AI will generate the correct SQL queries, execute them, and provide easy-to-understand results.

---

## Workflow
<img width="744" height="492" alt="NL2SQLBot_ Democratizing Data Access with AI-Powered Natural Language to SQL - visual selection (1)" src="https://github.com/user-attachments/assets/06d00b07-5d25-4f6c-bcc1-465f204ec804" />


### *figure not finalized 

This application follows a multi-stage workflow to convert natural language questions into SQL queries and visualize results. Here's how it works:

## **1. Initialization Phase**

- App starts in `__main__` block
- Loads available LLM models from Ollama (`get_available_models()`)
- Loads previous chat history from chat_history.json
- Creates the Gradio UI interface (`create_interface()`)

## **2. Connection Setup Phase**

**User actions:**

- Selects connection method (Connection String or individual fields)
- Enters SQL Server details (server name, authentication type)
- Clicks "Test Connection"

**Behind the scenes:**

- `test_connection()` → validates credentials → stores `SERVER_NAME`, `CURRENT_AUTH_TYPE`
- `get_available_databases()` → queries SQL Server for all databases
- Returns list of databases to user

## **3. Database Connection Phase**

**User actions:**

- Selects a database from dropdown
- Clicks "Connect Database"

**Behind the scenes:**

- `connect_to_database()` executes three optimized steps:
    1. **Schema Caching** - `load_schema_with_validation()` checks if cached schema is still valid (compares table count, modification date, cache age)
    2. **Schema Extraction** - If cache invalid, `get_database_schema()` extracts fresh schema (tables, columns, relationships)
    3. **Vector DB Creation** - `create_or_load_vector_db()` creates embeddings of schema using SentenceTransformer for semantic search

## **4. Few-Shot Examples Upload**

**User actions:**

- Uploads JSON file with example queries

**Behind the scenes:**

- `upload_few_shot_examples()` validates and stores examples in `FEW_SHOT_EXAMPLES` global variable
- These examples guide the LLM on the desired SQL style

## **5. Model Selection Phase**

**User actions:**

- Selects LLM model from dropdown
- Clicks "Connect Model"

**Behind the scenes:**

- `connect_model()` stores `LLM_MODEL` globally
- Validates connection to local Ollama service

## **6. Query Execution Phase (Core Workflow)**

When user submits a question:

```html
User Question
↓
find_relevant_tables()
→ Vector DB semantic search for related tables (top 5)
↓
build_enhanced_sql_prompt()
→ Combines schema info + few-shot examples + rules
↓
query_llm_with_reasoning()
→ Sends prompt to Ollama LLM
↓
extract_sql_and_reasoning()
→ Parses LLM response for SQL query + reasoning
↓
validate_and_sanitize_sql()
→ Uses SQLGlot to verify valid T-SQL syntax
→ Blocks dangerous commands (DROP, DELETE, INSERT, etc.)
↓
execute_safe_query()
→ Runs SQL against database via SQLAlchemy
→ Returns results as DataFrame
↓
convert_sql_results_to_nlp()
→ Uses LLM to summarize results in natural language
↓
generate_plotly_visualizations()
→ Analyzes DataFrame structure (numeric, categorical, datetime columns)
→ Creates up to 14 chart types (bar, pie, scatter, heatmap, gauge, etc.)
→ Scores each chart on 5 criteria (data utilization, variety, relevance, complexity, uniqueness)
→ Returns top 4 scored visualizations
↓
add_to_history()
→ Saves query, response, reasoning, SQL to chat history
```

## **7. History & Regeneration**

**User actions:**

- Selects previous query from history
- Optionally regenerates visualizations

**Behind the scenes:**

- `update_history_dropdown()` shows all queries for current database
- `regenerate_visuals_from_history()` re-executes old SQL and creates fresh charts

## **Key Global State Variables**

```html
SERVER_NAME              → Current SQL Server
CURRENT_DB              → Connected database
CURRENT_DB_ENGINE       → SQLAlchemy connection
LLM_MODEL               → Selected LLM model
SCHEMA_INFO             → Database schema details
VECTOR_DB               → Chroma vector store for semantic search
FEW_SHOT_EXAMPLES       → User-provided query examples
CHAT_HISTORY            → All previous interactions
```

## **Optimization Strategy**

- **Schema Caching**: Avoids expensive re-extraction if database unchanged
- **Vector DB Caching**: Only recreates embeddings when schema changes
- **Semantic Search**: Uses vector DB to find relevant tables faster than keyword matching

This creates a complete pipeline from natural language → SQL → results → visualizations!    
---

## Prerequisites (MUST DO BEFORE USING)

### **1. SQL Server ODBC Driver**

**Required for database connectivity**

- Download: https://go.microsoft.com/fwlink/?linkid=2249006
- Run the installer
- Choose "Download" then "Install" when prompted

### **2. Ollama (AI Engine)**

**Required for natural language understanding**

1. **Download & Install** from: https://ollama.ai/download
2. **Run Ollama** (it should appear in your system tray)
3. **Download a model** (open Command Prompt): (use cloud models to have faster results)
    
    ```bash
    ollama pull gpt-oss:20b-cloud
    ```
    

### **3. Database Access**

**You'll need:**

- SQL Server name/instance
- Database name(s) you want to query
- Authentication type:
    - Windows Authentication (recommended)
    - SQL Server Authentication (username/password)
    - Connection string

## Preparing Effective Few-Shot Examples

### **Golden Rules for Good Examples:**

1. **Be Specific**: Match your actual database structure
2. **Cover Common Questions**: Include examples for frequent queries
3. **Show Variety**: Different question styles, different SQL patterns

---

## Pro Tips for Best Results

### **Writing Questions:**

- **Be Specific**: "sales in Q3 2024" not "show me sales"
- **Include Context**: "products sold in New York stores"
- **Use Natural Language**: "who are our top 10 customers by purchase amount"

### **Database Connection:**

- Start with **Windows Authentication** if available
- Test connection to **master** database first
- Use **TrustServerCertificate=True** for local development

### **AI Model Selection:**

- **For local models**: Use `llama:3.2:1b` or `sqlcoder:15b`
- **For cloud models**: Use smaller models like  `deepseek-v3.1:671b-cloud`


`- **Note: Cloud models send prompts to external servers - check your data security policies**`


## Troubleshooting

### **Quick Fixes:**

- **Restart everything**: Close app, stop Ollama, restart both
- **Check logs**: Review Command Prompt window for error messages
- **Reinstall**: Run `install.bat` again with fresh download

---

## File Structure

After installation:

```
SQL_Assistant/
├── venv/                    # Python virtual environment
├── schema_cache_*.json      # Cached database schemas
├── vector_db_*/            # Vector database stores
├── chat_history.json       # Your query history
├── few_shot_examples.json  # Your training examples
├── app.py                  # Main application
├── install.bat            # Setup script
└── start.bat             # Launcher script


---

## Support & Resources

### **For Help:**

1. Check error messages in the Command Prompt window
2. Review the installation checklist above
3. Ensure all prerequisites are installed

### **Need Better Examples?**

- Start with a good number of examples for better result
- Add more as you discover common queries
- Update your JSON file anytime

### **Performance Issues?**

- Try a smaller AI model
- Close other applications
- Use cloud models for faster query



