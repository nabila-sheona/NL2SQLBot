## Overview

SQL Assistant is an intelligent chatbot that allows you to query your SQL Server databases using plain English. No SQL knowledge required! Simply ask questions in natural language, and the AI will generate the correct SQL queries, execute them, and provide easy-to-understand results.

---

## Workflow
<img width="1105" height="648" alt="SQL Assistant Application - Detailed Code Workflow Report - visual selection" src="https://github.com/user-attachments/assets/e4ef695e-c586-41ae-92a5-29516404743c" />

### *figure not finalized 

## Quick Start Guide

### 1. **Download & Install**

1. **Download** the production package containing:
    - `install.bat` - One-time setup installer
    - `start.bat` - Daily application launcher
    - `app.py` - Core application
    - `requirements.txt` - Required Python packages
2. **Run `install.bat`** (Double-click it)
    - This will automatically:
        - Install Python 3.11 if needed
        - Create a virtual environment
        - Install all required packages
        - Set up necessary folders

1. **Complete the prerequisites** (see below) while installation runs
2. **Run `start.bat`** to launch the application

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

---

## Setup Workflow

### **Step 1: First Launch**

1. Run `start.bat`
2. Application opens in your browser (usually [http://localhost:7860](http://localhost:7860/))
3. You'll see three main connection sections

### **Step 2: Connect to Database**

### **Option A: Connection String (Recommended)**

1. Select "Connection String" method
2. Enter your full connection string:
    
    ```
    Server=YOUR_SERVER;Database=master;Trusted_Connection=True;TrustServerCertificate=True
    
    ```
    
3. Click "Test Connection"

### **Option B: Individual Fields**

1. Select "Individual Fields" method
2. Enter Server Name (e.g., "localhost\SQLEXPRESS")
3. Select Authentication Type
4. Enter credentials if using SQL Server Authentication
5. Click "Test Connection"

### **Step 3: Select Database**

1. After successful connection, databases appear in dropdown
2. **CRITICAL: Upload examples first** (see Step 4)
3. Select your target database
4. Click "Connect Database"

### **Step 4: Upload Training Examples (MUST DO)**

**Before connecting to any database, you MUST provide examples:**

1. **Create a JSON file** named `my_examples.json`:
    
    ```json
    {
      "few_shot_examples": [
        {
          "question": "show me total sales last month",
          "sql": "SELECT SUM(SalesAmount) as TotalSales FROM FactSales WHERE OrderDate >= DATEADD(month, -1, GETDATE())"
        },
        {
          "question": "**********************************************",
          "sql": "************************************************"
        }
      ]
    }
    
    ```
    
2. **In the app:**
    - Click "Choose File" under "Upload Few-Shot Examples JSON"
    - Select your `my_examples.json` file
    - Click "Load Examples"
    - Status should show "Loaded X few-shot examples successfully!"

### **Step 5: Connect AI Model**

1. Model dropdown shows available Ollama models
2. Select your installed model (e.g., "deepseek-coder:6.7b")
3. Click "Connect Model"

### **Step 6: Start Querying!**

Once all three are connected (Database , Model, Examples ), you can:

1. Type questions in the "Your Question" box
2. Click "Submit" or press Enter
3. View results in three formats:
    - **Summary**: Natural language explanation
    - **Data Table**: Raw results in table format
    - **Reasoning**: AI's thought process

---

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

- **For local models**: Use `sqlcoder:7b` or `sqlcoder:15b`
- **For cloud models**: Use smaller models like `deepseek-coder:6.7b`
- **For complex reasoning and faster query**: Use `deepseek-v3.1:671b-cloud`
- **For storage concern and speed(NOT RELIABLE)**: Use  `gpt-oss:20b-cloud`

`- **Note: Cloud models send prompts to external servers - check your data security policies**`

### **Performance Tips:**

1. **First query may be slow** - AI model needs to load
2. **Subsequent queries are faster** - model stays in memory
3. **Close other applications** if experiencing slowdowns
4. **Restart Ollama** if responses become slow

---

## Troubleshooting

### **Common Issues:**

### **1. "Cannot connect to Ollama"**

- Make sure Ollama is running (check system tray)
- Run `ollama serve` in Command Prompt
- Restart the application

### **2. "No databases found"**

- Check your connection string/credentials
- Ensure SQL Server is running
- Verify you have access permissions

### **3. "Model not responding"**

- Check if model is downloaded: `ollama list`
- Pull the model again: `ollama pull MODEL_NAME`
- Restart Ollama

### **4. "Please upload examples first"**

- You MUST upload few-shot examples before connecting
- Create valid JSON file (use provided templates)
- Click "Load Examples" after selecting file

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

```

---

## Daily Use Workflow

1. **Start Ollama** (runs in background)
2. **Double-click `start.bat`**
3. **Wait for browser to open**
4. **Ask questions naturally**
5. **Close browser when done**

**No need to reconnect** - your database and model settings are INSTALLED!

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

---

## Congratulations!

You're now ready to query databases with natural language! Start with simple questions, build up your few-shot examples based on actual use, and enjoy instant data insights without writing SQL.

**Remember**: The AI learns from your examples - better examples = better results!

---
