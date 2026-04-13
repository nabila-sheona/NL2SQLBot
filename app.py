import gradio as gr
import pandas as pd
import re
import json
import os
from datetime import datetime
import chromadb
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
import requests
import hashlib
import urllib.parse
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
try:
    import sqlglot
    SQLGLOT_AVAILABLE = True
    print("SQLGlot imported successfully")
except ImportError:
    SQLGLOT_AVAILABLE = False
    print("SQLGlot not available, running without SQL safety")

SERVER_NAME = None
CURRENT_DB = None
CURRENT_DB_ENGINE = None
LLM_MODEL = None
SCHEMA_INFO = None
VECTOR_DB = None
FEW_SHOT_EXAMPLES = []
CHAT_HISTORY = []
HISTORY_FILE = "chat_history.json"
CURRENT_AUTH_TYPE = None
CURRENT_USERNAME = None
CURRENT_PASSWORD = None

import numpy as np

def score_visualization(fig, df, chart_type):
    """
    Score a visualization based on multiple quality criteria.
    Higher score = better visualization.
    """
    score = 0
    
    try:
        # Base score for valid chart
        if fig is None:
            return -1
        
        # 1. Data utilization (30 points)
        # Reward charts that use more of the available data
        if chart_type in ['bar', 'pie', 'donut', 'treemap', 'funnel']:
            rows_used = len(df)
            if rows_used >= 5:
                score += 30
            elif rows_used >= 3:
                score += 20
            else:
                score += 10
        else:
            score += 25  # Other charts get default score
        
        # 2. Data variety (25 points)
        # Reward charts that show diverse insights
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        
        if chart_type in ['scatter', 'heatmap', 'correlation']:
            # Multi-dimensional analysis
            score += 25
        elif chart_type in ['combo', 'grouped_bar', 'stacked_area']:
            # Multiple metrics
            score += 20
        elif chart_type in ['time_series', 'line']:
            # Temporal patterns
            score += 18
        else:
            score += 15
        
        # 3. Relevance to data size (20 points)
        row_count = len(df)
        
        if chart_type == 'pie' and row_count > 10:
            score -= 10  # Pie charts bad for many categories
        elif chart_type == 'gauge' and row_count != 1:
            score -= 15  # Gauge only good for single value
        elif chart_type == 'bar' and row_count > 20:
            score -= 5   # Too many bars
        elif chart_type == 'scatter' and row_count < 10:
            score -= 5   # Not enough points for scatter
        else:
            score += 20  # Good fit
        
        # 4. Chart complexity (15 points)
        # Reward charts that show relationships/patterns
        if chart_type in ['scatter', 'heatmap', 'combo', 'waterfall']:
            score += 15  # Complex, insightful charts
        elif chart_type in ['time_series', 'grouped_bar']:
            score += 12  # Moderately complex
        else:
            score += 8   # Simple charts
        
        # 5. Uniqueness bonus (10 points)
        # Reward less common chart types for diversity
        if chart_type in ['waterfall', 'funnel', 'treemap', 'gauge']:
            score += 10
        elif chart_type in ['heatmap', 'combo']:
            score += 8
        else:
            score += 5
        
        return score
        
    except Exception as e:
        print(f"Error scoring {chart_type}: {e}")
        return 0


def generate_plotly_visualizations(df, target_charts=4):
    """
    Intelligently generate visualizations for any SQL query result.
    Returns the TOP 4 scored charts (best quality).
    """
    print(f"=== SMART VISUALIZATION SYSTEM WITH SCORING ===")
    print(f"DataFrame shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    
    if df.empty or len(df) < 1:
        print("Empty dataframe - returning placeholders")
        return [None, None, None, None]
    
    try:
        # Analyze data structure
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        datetime_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        
        print(f"Numeric: {numeric_cols}")
        print(f"Categorical: {categorical_cols}")
        print(f"Datetime: {datetime_cols}")
        
        candidate_charts = []  # Will store (fig, chart_type, score)
        
        base_layout = {
            'autosize': True,
            'margin': dict(l=50, r=50, t=60, b=50, pad=4),
            'hovermode': 'closest',
            'plot_bgcolor': 'rgba(250, 250, 250, 1)',
            'paper_bgcolor': 'white',
            'font': dict(family="Arial", size=12),
        }
        
        # === 1. TIME SERIES ===
        if datetime_cols and numeric_cols:
            for num_col in numeric_cols[:2]:
                try:
                    fig = px.line(
                        df, 
                        x=datetime_cols[0], 
                        y=num_col,
                        title=f"{num_col} Over Time",
                        markers=True
                    )
                    fig.update_layout(**base_layout)
                    score = score_visualization(fig, df, 'time_series')
                    candidate_charts.append((fig, 'time_series', score))
                    print(f"   Time series ({num_col}): Score = {score}")
                except Exception as e:
                    print(f"   Failed time series: {e}")
        
        # === 2. BAR CHART ===
        if categorical_cols and numeric_cols:
            try:
                cat_col = categorical_cols[0]
                num_col = numeric_cols[0]
                df_limited = df.nlargest(15, num_col) if len(df) > 15 else df
                
                fig = px.bar(
                    df_limited,
                    x=cat_col,
                    y=num_col,
                    title=f"{num_col} by {cat_col}",
                    text_auto='.2s',
                    color=num_col,
                    color_continuous_scale='blues'
                )
                fig.update_layout(
                    **base_layout,
                    xaxis={'categoryorder': 'total descending'},
                    coloraxis_showscale=False
                )
                fig.update_traces(textposition='outside')
                score = score_visualization(fig, df_limited, 'bar')
                candidate_charts.append((fig, 'bar', score))
                print(f"   Bar chart: Score = {score}")
            except Exception as e:
                print(f"   Failed bar chart: {e}")
        
        # === 3. PIE / DONUT ===
        if categorical_cols and numeric_cols and len(df) <= 10:
            try:
                cat_col = categorical_cols[0]
                num_col = numeric_cols[0]
                
                fig = px.pie(
                    df,
                    names=cat_col,
                    values=num_col,
                    title=f"{cat_col} Distribution",
                    hole=0.4
                )
                fig.update_layout(**base_layout)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                score = score_visualization(fig, df, 'donut')
                candidate_charts.append((fig, 'donut', score))
                print(f"   Donut chart: Score = {score}")
            except Exception as e:
                print(f"   Failed donut chart: {e}")
        
        # === 4. SCATTER ===
        if len(numeric_cols) >= 2:
            try:
                fig = px.scatter(
                    df,
                    x=numeric_cols[0],
                    y=numeric_cols[1],
                    title=f"{numeric_cols[1]} vs {numeric_cols[0]}",
                    trendline="ols",
                    opacity=0.7
                )
                fig.update_layout(**base_layout)
                score = score_visualization(fig, df, 'scatter')
                candidate_charts.append((fig, 'scatter', score))
                print(f"   Scatter plot: Score = {score}")
            except Exception as e:
                print(f"   Failed scatter plot: {e}")
        
        # === 5. HEATMAP ===
        if len(numeric_cols) >= 3:
            try:
                corr_matrix = df[numeric_cols].corr()
                fig = px.imshow(
                    corr_matrix,
                    title="Correlation Matrix",
                    text_auto='.2f',
                    color_continuous_scale='RdBu_r',
                    aspect='auto'
                )
                fig.update_layout(**base_layout)
                score = score_visualization(fig, df, 'heatmap')
                candidate_charts.append((fig, 'heatmap', score))
                print(f"   Heatmap: Score = {score}")
            except Exception as e:
                print(f"   Failed heatmap: {e}")
        
        # === 6. BOX ===
        if numeric_cols:
            try:
                fig = px.box(
                    df,
                    y=numeric_cols[0],
                    title=f"Distribution: {numeric_cols[0]}",
                    points="outliers"
                )
                fig.update_layout(**base_layout)
                score = score_visualization(fig, df, 'box')
                candidate_charts.append((fig, 'box', score))
                print(f"   Box plot: Score = {score}")
            except Exception as e:
                print(f"   Failed box plot: {e}")
        
        # === 7. HISTOGRAM ===
        if numeric_cols:
            try:
                fig = px.histogram(
                    df,
                    x=numeric_cols[0],
                    title=f"Distribution: {numeric_cols[0]}",
                    nbins=20,
                    marginal="box"
                )
                fig.update_layout(**base_layout)
                score = score_visualization(fig, df, 'histogram')
                candidate_charts.append((fig, 'histogram', score))
                print(f"   Histogram: Score = {score}")
            except Exception as e:
                print(f"   Failed histogram: {e}")
        
        # === 8. GROUPED BAR ===
        if categorical_cols and len(numeric_cols) >= 2:
            try:
                cat_col = categorical_cols[0]
                df_limited = df.head(10) if len(df) > 10 else df
                
                fig = px.bar(
                    df_limited,
                    x=cat_col,
                    y=numeric_cols[:min(3, len(numeric_cols))],
                    title="Multi-Metric Comparison",
                    barmode='group'
                )
                fig.update_layout(**base_layout)
                score = score_visualization(fig, df_limited, 'grouped_bar')
                candidate_charts.append((fig, 'grouped_bar', score))
                print(f"   Grouped bar: Score = {score}")
            except Exception as e:
                print(f"   Failed grouped bar: {e}")
        
        # === 9. TREEMAP ===
        if categorical_cols and numeric_cols and len(df) <= 20:
            try:
                value_counts = df[categorical_cols[0]].value_counts().head(10)
                
                fig = px.treemap(
                    names=value_counts.index,
                    parents=[''] * len(value_counts),
                    values=value_counts.values,
                    title=f"Hierarchical View: {categorical_cols[0]}"
                )
                fig.update_layout(**base_layout)
                score = score_visualization(fig, df, 'treemap')
                candidate_charts.append((fig, 'treemap', score))
                print(f"   Treemap: Score = {score}")
            except Exception as e:
                print(f"   Failed treemap: {e}")
        
        # === 10. FUNNEL ===
        if categorical_cols and numeric_cols and len(df) <= 8:
            try:
                cat_col = categorical_cols[0]
                num_col = numeric_cols[0]
                df_sorted = df.sort_values(by=num_col, ascending=False).head(8)
                
                fig = go.Figure(go.Funnel(
                    y=df_sorted[cat_col],
                    x=df_sorted[num_col],
                    textinfo="value+percent initial"
                ))
                fig.update_layout(title="Funnel Analysis", **base_layout)
                score = score_visualization(fig, df_sorted, 'funnel')
                candidate_charts.append((fig, 'funnel', score))
                print(f"   Funnel: Score = {score}")
            except Exception as e:
                print(f"   Failed funnel chart: {e}")
        
        # === 11. GAUGE ===
        if len(numeric_cols) >= 1 and len(df) == 1:
            try:
                num_col = numeric_cols[0]
                value = df[num_col].iloc[0]
                max_val = value * 1.5 if value > 0 else 100
                
                fig = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=value,
                    title={'text': f"KPI: {num_col}"},
                    gauge={
                        'axis': {'range': [0, max_val]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, max_val*0.5], 'color': "lightgray"},
                            {'range': [max_val*0.5, max_val*0.75], 'color': "gray"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': max_val*0.9
                        }
                    }
                ))
                fig.update_layout(**base_layout)
                score = score_visualization(fig, df, 'gauge')
                candidate_charts.append((fig, 'gauge', score))
                print(f"   Gauge: Score = {score}")
            except Exception as e:
                print(f"   Failed gauge chart: {e}")
        
        # === 12. WATERFALL ===
        if categorical_cols and numeric_cols and 3 <= len(df) <= 15:
            try:
                cat_col = categorical_cols[0]
                num_col = numeric_cols[0]
                
                fig = go.Figure(go.Waterfall(
                    name="Waterfall",
                    orientation="v",
                    measure=["relative"] * len(df),
                    x=df[cat_col].tolist(),
                    y=df[num_col].tolist()
                ))
                fig.update_layout(title="Waterfall Chart", **base_layout)
                score = score_visualization(fig, df, 'waterfall')
                candidate_charts.append((fig, 'waterfall', score))
                print(f"   Waterfall: Score = {score}")
            except Exception as e:
                print(f"   Failed waterfall chart: {e}")
        
        # === 13. COMBO ===
        if categorical_cols and len(numeric_cols) >= 2:
            try:
                cat_col = categorical_cols[0]
                df_limited = df.head(12) if len(df) > 12 else df
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_limited[cat_col],
                    y=df_limited[numeric_cols[0]],
                    name=numeric_cols[0],
                    marker_color='lightblue'
                ))
                fig.add_trace(go.Scatter(
                    x=df_limited[cat_col],
                    y=df_limited[numeric_cols[1]],
                    name=numeric_cols[1],
                    mode='lines+markers',
                    yaxis='y2'
                ))
                fig.update_layout(
                    title="Combo Chart (Bar + Line)",
                    **base_layout,
                    yaxis=dict(title=numeric_cols[0]),
                    yaxis2=dict(title=numeric_cols[1], overlaying='y', side='right')
                )
                score = score_visualization(fig, df_limited, 'combo')
                candidate_charts.append((fig, 'combo', score))
                print(f"   Combo chart: Score = {score}")
            except Exception as e:
                print(f"   Failed combo chart: {e}")
        
        # === 14. STACKED AREA ===
        if datetime_cols and len(numeric_cols) >= 2:
            try:
                fig = px.area(
                    df,
                    x=datetime_cols[0],
                    y=numeric_cols[:min(3, len(numeric_cols))],
                    title="Stacked Area Chart",
                )
                fig.update_layout(**base_layout)
                score = score_visualization(fig, df, 'stacked_area')
                candidate_charts.append((fig, 'stacked_area', score))
                print(f"   Stacked area: Score = {score}")
            except Exception as e:
                print(f"  Failed stacked area: {e}")
        
        
        
        print(f"\n{'='*50}")
        print(f"Generated {len(candidate_charts)} candidate visualizations")
        
        # ========================================
        # SCORING & SELECTION: Pick top 4 by score
        # ========================================
        if len(candidate_charts) > 0:
            # Sort by score (descending)
            candidate_charts.sort(key=lambda x: x[2], reverse=True)
            
            print("\n RANKING (Top to Bottom):")
            for i, (fig, chart_type, score) in enumerate(candidate_charts[:10], 1):
                marker = "*" if i <= target_charts else "  "
                print(f"{marker} #{i}: {chart_type.upper()} - Score: {score}")
            
            # Select top N charts
            top_charts = [chart[0] for chart in candidate_charts[:target_charts]]
            
            # Fill with placeholders if needed
            while len(top_charts) < target_charts:
                apology_fig = go.Figure()
                apology_fig.update_layout(
                    **base_layout,
                    title="<b>Chart Unavailable</b>",
                    annotations=[dict(
                        text="Sorry! Not enough data patterns<br>to generate this visualization.",
                        xref="paper",
                        yref="paper",
                        x=0.5,
                        y=0.5,
                        showarrow=False
                    )],
                    xaxis={'visible': False},
                    yaxis={'visible': False}
                )
                top_charts.append(apology_fig)
            
            print(f"\n Returning TOP {len(top_charts)} visualizations by score")
            return top_charts
        
        else:
            # No charts generated
            print("No visualizations could be generated")
            return [None, None, None, None]

    except Exception as e:
        print(f"Visualization error: {e}")
        import traceback
        traceback.print_exc()
        return [None, None, None, None]

def build_connection_string(auth_type, server, database=None, username=None, password=None):
    """
    Build connection string based on authentication type
    """
    conn_parts = []

    if server:
        conn_parts.append(f"Server={server}")

    if database:
        conn_parts.append(f"Database={database}")
    else:
        conn_parts.append("Database=master")

    if auth_type == "Windows Authentication":
        conn_parts.append("Integrated Security=True")
        conn_parts.append("Trusted_Connection=yes")
        
    elif auth_type == "SQL Server Authentication":
        if username and password:
            conn_parts.append(f"User Id={username}")
            conn_parts.append(f"Password={password}")
        else:
            raise ValueError("Username and password required for SQL Server Authentication")
        conn_parts.append("Integrated Security=False")

    conn_parts.append("TrustServerCertificate=True")
    conn_parts.append("Encrypt=True")
    
    return ";".join(conn_parts)

def parse_connection_string(conn_str):
    """
    Parse a full connection string to extract components
    """
    params = {}
    for part in conn_str.strip().split(';'):
        if '=' in part:
            key, value = part.split('=', 1)
            params[key.strip().lower()] = value.strip()
    
    # Extract server
    server = params.get('data source') or params.get('server') or params.get('address')
    
    # Determine auth type
    if params.get('integrated security', '').lower() == 'true' or params.get('trusted_connection', '').lower() == 'yes':
        auth_type = "Windows Authentication"
    elif params.get('user id') or params.get('uid'):
        auth_type = "SQL Server Authentication"
    else:
        auth_type = "Windows Authentication"  # Default
    
    # Extract credentials if present
    username = params.get('user id') or params.get('uid')
    password = params.get('password') or params.get('pwd')
    
    # Extract database if present
    database = params.get('database') or params.get('initial catalog')
    
    return {
        'server': server,
        'auth_type': auth_type,
        'username': username,
        'password': password,
        'database': database
    }

def get_engine_from_connection(auth_type, server, database, username=None, password=None):
    """
    Create SQLAlchemy engine based on authentication type
    """
    try:
        conn_str = build_connection_string(auth_type, server, database, username, password)
        
        if auth_type == "Windows Authentication":
            pyodbc_conn_str = f"mssql+pyodbc://{server}/{database}?trusted_connection=yes&driver=ODBC+Driver+17+for+SQL+Server"
        elif auth_type == "SQL Server Authentication":
            pyodbc_conn_str = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
        else:
            pyodbc_conn_str = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(conn_str)}"
        
        engine = create_engine(
            pyodbc_conn_str,
            pool_pre_ping=True,
            echo=False,
            connect_args={
                "timeout": 10,
                "autocommit": True
            } if "ActiveDirectory" in auth_type else {}
        )
        
        return engine
    except Exception as e:
        print(f"Error creating engine: {e}")
        raise e

def test_connection(auth_type, server, username=None, password=None, connection_string=None):
    """
    Test connection - accepts either individual parameters OR a connection string
    """
    global SERVER_NAME, CURRENT_AUTH_TYPE, CURRENT_USERNAME, CURRENT_PASSWORD
    
    try:
        # If connection string is provided, parse it
        if connection_string and connection_string.strip():
            parsed = parse_connection_string(connection_string)
            auth_type = parsed['auth_type']
            server = parsed['server']
            username = parsed['username']
            password = parsed['password']
        
        # Validate inputs
        if not server or not server.strip():
            return False, "Please enter a server name"
        
        if auth_type in ["SQL Server Authentication"]:
            if not username or not username.strip():
                return False, "Please enter username"
            if not password or not password.strip():
                return False, "Please enter password"
        
        # Test connection to master database
        engine = get_engine_from_connection(auth_type, server, "master", username, password)
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Store globally for later use
        SERVER_NAME = server
        CURRENT_AUTH_TYPE = auth_type
        CURRENT_USERNAME = username
        CURRENT_PASSWORD = password
        
        print(f"Connection successful to server: {server}")
      
        return True, f"Connected to server: {server}"
        
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        print(f"Connection test failed: {e}")
        return False, error_msg

def get_available_databases():
    """
    Dynamically detect available databases
    """
    global SERVER_NAME, CURRENT_AUTH_TYPE, CURRENT_USERNAME, CURRENT_PASSWORD
    
    if not SERVER_NAME:
        print("No server connection established")
        return []
    
    try:
        # Create engine for master database
        engine = get_engine_from_connection(CURRENT_AUTH_TYPE, SERVER_NAME, "master", CURRENT_USERNAME, CURRENT_PASSWORD)
        
        with engine.connect() as conn:
            # Query for user databases
            query = """
            SELECT name 
            FROM sys.databases 
            WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
              AND state = 0  -- ONLINE
              AND HAS_DBACCESS(name) = 1  -- We have access
            ORDER BY name
            """
            
            result = conn.execute(text(query))
            databases = [row[0] for row in result]
            
            # Test connection to each database
            valid_databases = []
            for db in databases:
                try:
                    test_engine = get_engine_from_connection(CURRENT_AUTH_TYPE, SERVER_NAME, db, CURRENT_USERNAME, CURRENT_PASSWORD)
                    with test_engine.connect() as test_conn:
                        test_conn.execute(text("SELECT 1"))
                    valid_databases.append(db)
                    test_engine.dispose()
                except Exception as e:
                    print(f"  Skipping database '{db}' - {e}")
                    continue
            
            print(f"Found {len(valid_databases)} accessible databases: {valid_databases}")
            return valid_databases
            
    except Exception as e:
        print(f"Error detecting databases: {e}")
        return []

def get_database_info(database_name, engine):
    """
    Get basic information about the database
    """
    try:
        with engine.connect() as conn:
            # Get table count
            table_query = """
            SELECT COUNT(*) as table_count
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            """
            table_result = conn.execute(text(table_query))
            table_count = table_result.fetchone()[0]
            
            # Get row count estimate
            row_query = f"""
            SELECT SUM(p.rows) as row_count
            FROM sys.tables t
            INNER JOIN sys.partitions p ON t.object_id = p.object_id
            WHERE p.index_id IN (0,1)
            """
            row_result = conn.execute(text(row_query))
            row_count = row_result.fetchone()[0] or 0
            
            # Get last modified date
            mod_query = """
            SELECT MAX(modify_date) as last_modified
            FROM sys.objects
            WHERE type = 'U'
            """
            mod_result = conn.execute(text(mod_query))
            last_modified = mod_result.fetchone()[0]
            
            info = {
                "name": database_name,
                "table_count": table_count,
                "estimated_rows": row_count,
                "last_modified": last_modified.isoformat() if last_modified else "Unknown"
            }
            
            print(f"Database info for {database_name}: {table_count} tables, ~{row_count:,} rows")
            return info
            
    except Exception as e:
        print(f"Error getting database info: {e}")
        return {
            "name": database_name,
            "table_count": 0,
            "estimated_rows": 0,
            "last_modified": "Unknown"
        }

def get_primary_keys(engine, table_name):
    try:
        query = f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + '.' + CONSTRAINT_NAME), 'IsPrimaryKey') = 1
            AND TABLE_NAME = '{table_name}'
        ORDER BY ORDINAL_POSITION
        """
        with engine.connect() as conn:
            result = conn.execute(text(query))
            return [row[0] for row in result]
    except Exception as e:
        print(f"Error getting primary keys for {table_name}: {e}")
        return []

def get_database_schema(engine, database_name):
    try:
        schema_query = """
        SELECT
            OBJECT_NAME(c.object_id) as object_name,
            c.name as column_name,
            ty.name as data_type,
            c.max_length,
            c.is_nullable,
            CASE
                WHEN o.type = 'U' THEN 'TABLE'
                WHEN o.type = 'V' THEN 'VIEW'
            END as object_type
        FROM sys.columns c
        JOIN sys.objects o ON c.object_id = o.object_id
        JOIN sys.types ty ON c.user_type_id = ty.user_type_id
        WHERE o.is_ms_shipped = 0
          AND o.type = 'U'
        ORDER BY object_name, c.column_id
        """
        
        fk_query = """
        SELECT
            OBJECT_NAME(f.parent_object_id) AS source_table,
            COL_NAME(f.parent_object_id, fc.parent_column_id) AS source_column,
            OBJECT_NAME(f.referenced_object_id) AS target_table,
            COL_NAME(f.referenced_object_id, fc.referenced_column_id) AS target_column
        FROM sys.foreign_keys f
        INNER JOIN sys.foreign_key_columns fc 
            ON f.object_id = fc.constraint_object_id
        ORDER BY source_table, target_table
        """
        
        with engine.connect() as conn:
            result = pd.read_sql(text(schema_query), conn)
            fk_result = pd.read_sql(text(fk_query), conn)
        
        schema_info = {
            'extraction_time': datetime.now().isoformat(),
            'database': database_name,
            'objects': {},
            'relationships': [],
            'sample_data': {}
        }
        
        tables = result['object_name'].unique()
        
        for obj_name in tables:
            obj_data = result[result['object_name'] == obj_name]
            obj_type = obj_data.iloc[0]['object_type']
           
            schema_info['objects'][obj_name] = {
                'type': obj_type,
                'columns': []
            }
            
            for _, col in obj_data.iterrows():
                schema_info['objects'][obj_name]['columns'].append({
                    'name': col['column_name'],
                    'data_type': col['data_type'],
                    'is_nullable': bool(col['is_nullable']),
                    'max_length': int(col['max_length']) if col['max_length'] else None
                })
            
            schema_info['objects'][obj_name]['primary_keys'] = get_primary_keys(engine, obj_name)
            
            try:
                sample_data = pd.read_sql(text(f"SELECT TOP 3 * FROM {obj_name}"), conn)
                schema_info['sample_data'][obj_name] = sample_data.to_dict('records')
            except:
                schema_info['sample_data'][obj_name] = []
        
        for _, fk in fk_result.iterrows():
            schema_info['relationships'].append({
                'source_table': fk['source_table'],
                'source_column': fk['source_column'],
                'target_table': fk['target_table'],
                'target_column': fk['target_column']
            })
        
        print(f"Schema loaded: {len(schema_info['objects'])} TABLES")
        print(f"Foreign keys: {len(schema_info['relationships'])} relationships")
        return schema_info
    except Exception as e:
        print(f"Schema extraction error: {e}")
        return {'objects': {}, 'relationships': [], 'sample_data': {}}

def compute_schema_hash(schema_info):
    try:
        schema_signature = []
        for table_name in sorted(schema_info.get('objects', {}).keys()):
            table_info = schema_info['objects'][table_name]
            columns = sorted([col['name'] for col in table_info['columns']])
            schema_signature.append(f"{table_name}:{','.join(columns)}")
        
        signature_str = "|".join(schema_signature)
        return hashlib.md5(signature_str.encode()).hexdigest()
    except Exception as e:
        print(f"Error computing schema hash: {e}")
        return None

def get_database_last_modified(engine):
    try:
        query = """
        SELECT MAX(modify_date) as last_modified
        FROM sys.objects
        WHERE type = 'U'
        """
        with engine.connect() as conn:
            result = conn.execute(text(query))
            row = result.fetchone()
            if row and row[0]:
                return row[0].isoformat()
        return None
    except Exception as e:
        print(f"Error getting database modified date: {e}")
        return None

def save_schema_with_metadata(schema_info, database_name, db_last_modified):
    try:
        cache_file = f"schema_cache_{database_name}.json"
        
        schema_with_meta = {
            "metadata": {
                "database_name": database_name,
                "cached_at": datetime.now().isoformat(),
                "db_last_modified": db_last_modified,
                "schema_hash": compute_schema_hash(schema_info),
                "table_count": len(schema_info.get('objects', {})),
                "relationship_count": len(schema_info.get('relationships', []))
            },
            "schema": schema_info
        }
        
        with open(cache_file, 'w') as f:
            json.dump(schema_with_meta, f, indent=2)
        
        print(f"Schema cached: {cache_file}")
        return True
    except Exception as e:
        print(f"Error saving schema metadata: {e}")
        return False     

def load_schema_with_validation(database_name, engine):
    """
    Load cached schema ONLY if it's still valid (saves time!)
    Returns: (schema_info, cache_status)
    """
    try:
        cache_file = f"schema_cache_{database_name}.json"
        
        # No cache? Must extract fresh schema
        if not os.path.exists(cache_file):
            print(f" No cache found for {database_name}")
            return None, "NO_CACHE"
        
        # Load cached data
        with open(cache_file, 'r') as f:
            cached_data = json.load(f)
        
        metadata = cached_data.get('metadata', {})
        schema_info = cached_data.get('schema', {})
        
        print(f" Cache found, validating...")
        
        # ===== VALIDATION 1: Table count =====
        try:
            with engine.connect() as conn:
                actual_table_query = """
                SELECT COUNT(*) as table_count
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE'
                """
                result = conn.execute(text(actual_table_query))
                actual_table_count = result.fetchone()[0]
                
                cached_table_count = metadata.get('table_count', 0)
                
                if actual_table_count != cached_table_count:
                    print(f" Table count changed: {cached_table_count} → {actual_table_count}")
                    return None, "SCHEMA_CHANGED"
                
                # ===== VALIDATION 2: Table names =====
                actual_tables_query = """
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
                """
                actual_tables_result = conn.execute(text(actual_tables_query))
                actual_table_names = set([row[0] for row in actual_tables_result])
                
                cached_table_names = set(schema_info.get('objects', {}).keys())
                
                if actual_table_names != cached_table_names:
                    added = actual_table_names - cached_table_names
                    removed = cached_table_names - actual_table_names
                    print(f" Table names changed:")
                    if added:
                        print(f"   New: {added}")
                    if removed:
                        print(f"   Removed: {removed}")
                    return None, "SCHEMA_CHANGED"
                
        except Exception as e:
            print(f" Error checking schema: {e}")
            return None, "ERROR"
        
        # ===== VALIDATION 3: Database modification date =====
        current_db_modified = get_database_last_modified(engine)
        cached_db_modified = metadata.get('db_last_modified')
        
        if current_db_modified and cached_db_modified:
            if current_db_modified > cached_db_modified:
                print(f" Database modified: {cached_db_modified} → {current_db_modified}")
                return None, "DB_MODIFIED"
        
        # ===== VALIDATION 4: Cache age =====
        cached_at = datetime.fromisoformat(metadata.get('cached_at', '2000-01-01'))
        cache_age_days = (datetime.now() - cached_at).days
        
        if cache_age_days > 7:
            print(f" Cache too old: {cache_age_days} days")
            return None, "CACHE_OLD"
        
        # ===== ALL VALIDATIONS PASSED! Use cache =====
        # Ensure backwards compatibility
        if 'sample_data' not in schema_info:
            schema_info['sample_data'] = {}
        
        for table_name, table_info in schema_info.get('objects', {}).items():
            if 'primary_keys' not in table_info:
                table_info['primary_keys'] = []
        
        print(f" Cache valid! Using cached schema")
        print(f"    Tables: {metadata.get('table_count')}")
        print(f"    Hash: {metadata.get('schema_hash')[:8]}...")
        print(f"    Age: {cache_age_days} days")
        
        return schema_info, "VALID"
        
    except Exception as e:
        print(f" Error loading cache: {e}")
        return None, "ERROR"


def create_or_load_vector_db(schema_info, database_name, force_recreate=False):
    """
    Load cached vector DB if schema unchanged (FAST!)
    Recreate only when force_recreate=True (schema changed)
    """
    try:
        vector_store_path = f"./vector_db_{database_name}"
        metadata_file = f"{vector_store_path}/metadata.json"
        
        # ===== FAST PATH: Use cached vector DB =====
        if not force_recreate and os.path.exists(vector_store_path):
            if os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r') as f:
                        vdb_metadata = json.load(f)
                    
                    current_hash = compute_schema_hash(schema_info)
                    cached_hash = vdb_metadata.get('schema_hash')
                    
                    if current_hash == cached_hash:
                        print(f" Vector DB valid! Loading cached version...")
                        client = chromadb.PersistentClient(path=vector_store_path)
                        collection = client.get_collection("schema_embeddings")
                        print(f"   Loaded {vdb_metadata.get('table_count')} tables from cache")
                        return collection
                    else:
                        print(f" Vector DB hash mismatch, will recreate")
                        
                except Exception as e:
                    print(f" Error reading vector DB metadata: {e}")
        
        # ===== SLOW PATH: Recreate vector DB =====
        print(f" {'Recreating' if force_recreate else 'Creating'} vector DB for {database_name}...")
        
        client = chromadb.PersistentClient(path=vector_store_path)
        
        # Delete old collection if exists
        try:
            client.delete_collection("schema_embeddings")
            print("   Deleted old collection")
        except:
            pass
        
        collection = client.create_collection("schema_embeddings")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        documents = []
        metadatas = []
        ids = []
        
        # Build embeddings from schema
        for table_name, table_info in schema_info['objects'].items():
            columns_desc = []
            for col in table_info['columns']:
                nullable = "NULL" if col['is_nullable'] else "NOT NULL"
                columns_desc.append(f"{col['name']} ({col['data_type']}) {nullable}")
            
            columns_text = ", ".join(columns_desc)
            primary_keys = table_info.get('primary_keys', [])
            pk_text = f"Primary Keys: {', '.join(primary_keys)}" if primary_keys else "No Primary Key"
            
            fks_for_table = [
                f"{fk['source_column']} -> {fk['target_table']}.{fk['target_column']}"
                for fk in schema_info['relationships']
                if fk['source_table'] == table_name
            ]
            fk_text = f"Foreign Keys: {', '.join(fks_for_table)}" if fks_for_table else "No Foreign Keys"
            
            flat_description = f"Table {table_name}: {columns_text}. {pk_text}. {fk_text}"
            
            documents.append(flat_description)
            metadatas.append({
                "table_name": table_name,
                "type": table_info['type'],
                "database": database_name,
                "column_count": len(table_info['columns']),
                "columns": ", ".join([col['name'] for col in table_info['columns']]),
                "primary_keys": ", ".join(primary_keys),
                "foreign_keys": ", ".join(fks_for_table)
            })
            ids.append(f"{database_name}_{table_name}")
        
        # Add to collection
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        
        # Save metadata for future validation
        vdb_metadata = {
            "database_name": database_name,
            "created_at": datetime.now().isoformat(),
            "schema_hash": compute_schema_hash(schema_info),
            "table_count": len(schema_info['objects'])
        }
        
        os.makedirs(vector_store_path, exist_ok=True)
        with open(metadata_file, 'w') as f:
            json.dump(vdb_metadata, f, indent=2)
        
        print(f" Vector DB created: {len(documents)} tables embedded")
        return collection
        
    except Exception as e:
        print(f" Vector DB error: {e}")
        import traceback
        traceback.print_exc()
        return None


def connect_to_database(database_name):
    """
    Optimized connection: Uses cache when possible, only recreates when necessary
    """
    global CURRENT_DB, CURRENT_DB_ENGINE, SCHEMA_INFO, VECTOR_DB, FEW_SHOT_EXAMPLES
    
    print(f"\n{'='*60}")
    print(f" Connecting to: {database_name}")
    print(f"{'='*60}")
    
    # Check prerequisites
    if len(FEW_SHOT_EXAMPLES) == 0:
        print(" No few-shot examples loaded")
        return f"Cannot connect to {database_name}: Please upload few-shot examples first."
    
    # Test connection
    success, result = test_database_connection(database_name)
    if not success:
        return f"Connection failed: {result}"
    
    engine = result
    CURRENT_DB = database_name
    CURRENT_DB_ENGINE = engine
    
    # Get database info
    db_info = get_database_info(database_name, engine)
    db_last_modified = get_database_last_modified(engine)
    
    print(f" Database info: {db_info['table_count']} tables, ~{db_info['estimated_rows']:,} rows")
    
    # ===== STEP 1: Try to use cached schema (FAST) =====
    schema_info, cache_status = load_schema_with_validation(database_name, engine)
    
    # ===== STEP 2: If cache invalid, extract fresh schema (SLOW) =====
    if cache_status != "VALID":
        print(f" Extracting fresh schema (Reason: {cache_status})...")
        schema_info = get_database_schema(engine, database_name)
        
        if not schema_info or not schema_info.get('objects'):
            return f"No tables found in {database_name}"
        
        save_schema_with_metadata(schema_info, database_name, db_last_modified)
        print(f" Schema extracted and saved to cache")
    
    SCHEMA_INFO = schema_info
    
    # ===== STEP 3: Load or recreate vector DB =====
    # Only force recreate if schema was just refreshed
    force_recreate = (cache_status != "VALID")
    
    if force_recreate:
        print(f" Schema changed, vector DB will be recreated")
    else:
        print(f" Schema unchanged, vector DB will be loaded from cache")
    
    vector_db = create_or_load_vector_db(schema_info, database_name, force_recreate)
    
    if not vector_db:
        return f"Connected to {database_name} but vector DB failed"
    
    VECTOR_DB = vector_db
    
    print(f"{'='*60}")
    print(f" Connection successful!")
    print(f"{'='*60}")
    
    # Build status message
    cache_emoji = " (cached)" if cache_status == "VALID" else " (refreshed)"
    vector_emoji = " (cached)" if not force_recreate else " (rebuilt)"
    
    return f"""Connected to: {database_name}
• Tables: {db_info['table_count']}
• Rows: ~{db_info['estimated_rows']:,}
• Modified: {db_info['last_modified']}
• Schema: {cache_emoji}
• Vector DB: {vector_emoji}
• Examples: {len(FEW_SHOT_EXAMPLES)} loaded

Ready for queries!"""


def update_upload_button_state(db_name):
    """Enable/disable upload button and file input based on database selection"""
    if db_name and db_name != "No databases found":
        return (
            gr.Button("Load Examples", variant="primary", size="sm", interactive=True),
            gr.File(interactive=True)  # Enable file upload
        )
    else:
        return (
            gr.Button("Load Examples", variant="secondary", size="sm", interactive=False),
            gr.File(interactive=False)  # Disable file upload
        )
    
def load_chat_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading history: {e}")
        return []

def add_to_history(db_name, user_message, bot_response, sql_query=None, reasoning=None):
    if any(error_indicator in bot_response.lower() for error_indicator in [
        "cannot generate",
        "could not generate", 
        "no relevant tables",
        "error:",
        "failed to connect",
        "please select",
        "please connect"
     ]):
        print("Not saving to history (error/failure)")
        return
    
    if not bot_response or not user_message:
        return
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "database": db_name,
        "user_message": user_message,
        "bot_response": bot_response,
        "sql_query": sql_query,
        "reasoning": reasoning or "No reasoning provided"
    }
    CHAT_HISTORY.append(entry)
    
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(CHAT_HISTORY, f, indent=2)
        print(f"Chat history saved ({len(CHAT_HISTORY)} messages)")
    except Exception as e:
        print(f"Error saving history: {e}")



def query_llm_with_reasoning(prompt, include_reasoning=False):
    try:
        if not LLM_MODEL:
            print("No LLM model selected")
            return None
            
        if include_reasoning:
            reasoning_prompt = prompt + "\n\nAfter generating the SQL query, provide a brief reasoning explaining:\n1. Why you chose these tables\n2. Why you used these specific JOINs\n3. Why you selected these columns\n4. Any assumptions made\n\nFormat your response as:\nSQL: [your sql query]\nREASONING: [your reasoning]"
        else:
            reasoning_prompt = prompt
        
        print(f"Using model: {LLM_MODEL}")
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': LLM_MODEL,
                'prompt': reasoning_prompt,
                'stream': False,
                'options': {'temperature': 0.0}
            },
            timeout=300
        )
        
        if response.status_code == 200:
            return response.json()['response'].strip()
        else:
            print(f"LLM error: {response.status_code}")
            return None
    except Exception as e:
        print(f"LLM connection error: {e}")
        return None


def build_enhanced_sql_prompt(user_question, relevant_tables):
    try:
        all_examples = []
        
        if FEW_SHOT_EXAMPLES:
            all_examples = FEW_SHOT_EXAMPLES
            print(f"Using {len(all_examples)} examples from memory")
        elif os.path.exists('few_shot_examples.json'):
            with open('few_shot_examples.json', 'r') as f:
                examples_data = json.load(f)
                all_examples = examples_data.get('few_shot_examples', [])
            print(f"Using {len(all_examples)} examples from file")
        else:
            print("No examples found")
            all_examples = []
    
        question_lower = user_question.lower()
        relevant_examples = []
        
        for example in all_examples:
            example_question = example['question'].lower()
            user_words = set(question_lower.split())
            example_words = set(example_question.split())
            common_words = user_words.intersection(example_words)
            
            if len(common_words) >= 2:
                relevant_examples.append(example)
                if len(relevant_examples) >= 3:
                    break
        
        if not relevant_examples:
            relevant_examples = all_examples[:3]
        
        schema_context = "=== DATABASE SCHEMA ===\n"
        schema_context += f"Database: {CURRENT_DB}\n\n"
        
        for table_name in relevant_tables[:5]:
            if table_name in SCHEMA_INFO.get('objects', {}):
                table_info = SCHEMA_INFO['objects'][table_name]
                columns = [col['name'] for col in table_info['columns']]
                
                schema_context += f"{table_name}:\n"
                schema_context += f"  Columns: {', '.join(columns[:10])}"
                if len(columns) > 10:
                    schema_context += f"... and {len(columns)-10} more"
                schema_context += "\n"
                
                if table_info.get('primary_keys'):
                    schema_context += f"  Primary Keys: {', '.join(table_info['primary_keys'])}\n"
                
                schema_context += "---\n"
        
        examples_section = "\n=== EXAMPLE QUERIES ===\n"
        for i, ex in enumerate(relevant_examples, 1):
            examples_section += f"\nExample {i}:\n"
            examples_section += f"Question: {ex['question']}\n"
            examples_section += f"SQL: {ex['sql']}\n"
        
        rules_section = """
=== IMPORTANT RULES ===
0. must learn from examples, will help you to understand what user meant better.
1. Use ONLY tables and columns listed above
2. Use SQL Server syntax (TOP instead of LIMIT)
3. Use INNER JOIN for required relationships
4. Use SUM(), COUNT(), AVG() with GROUP BY
5. End query with semicolon
6. If impossible, say "CANNOT_GENERATE"
7. If your assumed word isnt available as a database table or column, whichever is the case, try adding something before or after or maybe try to use something similar to like of sql or maybe try to find with the synonym of the word.
8. should be aware of all kind of t-sql query and what can mean what from natural language to sql.
"""
        
        prompt_text = f"""{rules_section}
{schema_context}
{examples_section}

=== QUESTION ===
Question: "{user_question}"

Generate ONLY the SQL query (no explanations):
SQL:"""
        
        return prompt_text
    except Exception as e:
        print(f"Error building prompt: {e}")
        return ""

def find_relevant_tables(question, top_k=5):
    if not VECTOR_DB:
        return []
    
    try:
        results = VECTOR_DB.query(query_texts=[question], n_results=top_k)
        if results['ids'] and len(results['ids']) > 0:
            table_ids = results['ids'][0]
            table_names = []
            for table_id in table_ids:
                parts = table_id.split('_')
                if len(parts) > 1:
                    table_name = '_'.join(parts[1:])
                else:
                    table_name = table_id
                table_names.append(table_name)
            
            print(f"Found relevant tables: {table_names}")
            return table_names
        return []
    except Exception as e:
        print(f"Error finding tables: {e}")
        return []

def validate_and_sanitize_sql(sql_query):
    if not SQLGLOT_AVAILABLE:
        print("WARNING: Running without SQLGlot validation")
        return sql_query
    
    try:
        parsed = sqlglot.parse_one(sql_query, read='tsql')
        
        dangerous = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'TRUNCATE', 'CREATE', 'EXEC']
        query_upper = sql_query.upper()
        
        if not query_upper.strip().startswith('SELECT'):
            raise ValueError("Only SELECT queries allowed")
        
        for keyword in dangerous:
            if f" {keyword} " in query_upper:
                raise ValueError(f"Blocked: {keyword}")
        
        print("SQL validation passed")
        return sql_query
    except sqlglot.errors.ParseError as e:
        print(f"SQL parsing error: {e}")
        raise ValueError(f"Invalid SQL syntax: {str(e)}")
    except Exception:
        if not sql_query.upper().strip().startswith('SELECT'):
            raise ValueError("Only SELECT allowed")
        return sql_query

def execute_safe_query(sql_query):
    if not CURRENT_DB_ENGINE:
        raise Exception("No database connected")
    
    try:
        safe_sql = validate_and_sanitize_sql(sql_query)
        
        with CURRENT_DB_ENGINE.connect() as conn:
            result = pd.read_sql(text(safe_sql), conn)
        
        return result
    except Exception as e:
        print(f"Execution error: {e}")
        return pd.DataFrame()

def extract_sql_and_reasoning(llm_response):
    if not llm_response:
        return None, None
    
    if "CANNOT_GENERATE" in llm_response:
        return None, llm_response
    
    sql_query = None
    reasoning = None
    
    lines = llm_response.strip().split('\n')
    sql_lines = []
    reasoning_lines = []
    in_sql = False
    in_reasoning = False
    
    for line in lines:
        line_stripped = line.strip()
        
        if line_stripped.upper().startswith('SQL:'):
            in_sql = True
            in_reasoning = False
            sql_lines.append(line_stripped[4:].strip())
        elif line_stripped.upper().startswith('REASONING:'):
            in_sql = False
            in_reasoning = True
            reasoning_lines.append(line_stripped[10:].strip())
        elif in_sql:
            sql_lines.append(line_stripped)
        elif in_reasoning:
            reasoning_lines.append(line_stripped)
    
    if sql_lines:
        sql_query = '\n'.join(sql_lines)
        sql_query = re.sub(r'```sql', '', sql_query)
        sql_query = re.sub(r'```\s*', '', sql_query).strip()
    
    if reasoning_lines:
        reasoning = '\n'.join(reasoning_lines)
    
    if sql_query and SQLGLOT_AVAILABLE:
        try:
            parsed = sqlglot.parse_one(sql_query, read='tsql')
            if isinstance(parsed, sqlglot.exp.Select):
                formatted_sql = sqlglot.transpile(sql_query, read='tsql', write='tsql', pretty=True)[0]
                sql_query = formatted_sql
        except:
            pass
    
    if sql_query and not sql_query.upper().startswith('SELECT'):
        return None, None
    
    return sql_query, reasoning

def convert_sql_results_to_nlp(df, question, sql):
    if df.empty:
        return "No results found for your query."
    
    try:
        rows_count = len(df)
        cols_count = len(df.columns)
        column_names = ", ".join(df.columns.tolist())
        
        if rows_count <= 10:
            data_summary = df.to_string(index=False)
        else:
            data_summary = df.head(10).to_string(index=False) + f"\n... and {rows_count - 10} more rows"
        
        nlp_prompt = f"""Convert the following database query results into a clear, natural language summary.
Be concise but informative. Highlight the key insights and important values.
Question asked: {question}
Query results (columns: {column_names}):
{data_summary}
Provide a natural language summary of these results in 2-3 sentences:"""
        
        print("Converting results to natural language...")
        nlp_response = query_llm_with_reasoning(nlp_prompt, include_reasoning=False)
        
        if nlp_response:
            print("Natural language conversion successful!")
            return nlp_response.strip()
        else:
            print("NLP conversion failed, returning formatted results")
            return df.to_string(index=False)
    except Exception as e:
        print(f"Error converting to NLP: {e}")
        return df.to_string(index=False)

def get_dynamic_answer(question):
    sql_query = None
    reasoning = None
    try:
        if not CURRENT_DB:
            return "Please select and connect to a database first.", pd.DataFrame(), None
        
        if not VECTOR_DB:
            return f"Vector DB not loaded for {CURRENT_DB}. Please reconnect.", pd.DataFrame(), None
        
        print(f"\nQuestion: {question}")
        print(f"Database: {CURRENT_DB}")
        
        relevant_tables = find_relevant_tables(question, top_k=5)
        
        if not relevant_tables:
            return "No relevant tables found. Try rephrasing.", pd.DataFrame(), None
        
        prompt = build_enhanced_sql_prompt(question, relevant_tables)
        
        print("\nGenerating SQL with reasoning...")
        llm_response = query_llm_with_reasoning(prompt, include_reasoning=True)
        
        if llm_response and "CANNOT_GENERATE" in llm_response:
            defeat_message = f"{llm_response}\n\nThe required columns do not exist in the database schema."
            add_to_history(CURRENT_DB, question, defeat_message, None, "Could not generate query - columns not found")
            return defeat_message, pd.DataFrame(), None
        
        if llm_response:
            sql_query, reasoning = extract_sql_and_reasoning(llm_response)
        
        if not sql_query:
            failure_msg = "Could not generate valid SQL for that question. The schema may not support this query."
            add_to_history(CURRENT_DB, question, failure_msg, None, reasoning or "No reasoning available")
            return failure_msg, pd.DataFrame(), reasoning
        
        print(f"Executing SQL...")  
        results = execute_safe_query(sql_query)
    
        if results.empty:
            response_text = "No results found."
        else:
            response_text = convert_sql_results_to_nlp(results, question, sql_query)
            add_to_history(CURRENT_DB, question, response_text, sql_query, reasoning)
        
        return response_text, results, reasoning
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        add_to_history(CURRENT_DB, question, error_msg, sql_query, reasoning)
        return error_msg, pd.DataFrame(), reasoning
def upload_few_shot_examples(file):
    """
    Handle uploaded few-shot examples JSON file
    """
    global FEW_SHOT_EXAMPLES
    
    try:
        if file is None:
            FEW_SHOT_EXAMPLES = []
            return "No file uploaded", gr.File(value=None), gr.Button("Load Examples", variant="primary", size="sm", interactive=True)
        
        # Read the uploaded file
        with open(file.name, 'r') as f:
            data = json.load(f)
        
        # Validate structure
        if 'few_shot_examples' not in data:
            FEW_SHOT_EXAMPLES = []
            return "Invalid format: JSON must contain 'few_shot_examples' key", gr.File(value=None), gr.Button("Load Examples", variant="primary", size="sm", interactive=True)
        
        examples = data.get('few_shot_examples', [])
        
        # Validate each example has required fields
        for i, example in enumerate(examples):
            if 'question' not in example or 'sql' not in example:
                FEW_SHOT_EXAMPLES = []
                return f"Invalid format: Example {i+1} missing 'question' or 'sql' field", gr.File(value=None), gr.Button("Load Examples", variant="primary", size="sm", interactive=True)
        
        # Save to global variable
        FEW_SHOT_EXAMPLES = examples
        
        # Save to a file that build_enhanced_sql_prompt() can read
        with open('few_shot_examples.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Loaded {len(examples)} examples (saved to few_shot_examples.json)")
        
        return f"Loaded {len(examples)} examples", gr.File(value=file.name), gr.Button("Examples Loaded", variant="secondary", size="sm", interactive=False)
        
    except json.JSONDecodeError:
        FEW_SHOT_EXAMPLES = []
        return "Invalid JSON file format", gr.File(value=None), gr.Button("Load Examples", variant="primary", size="sm", interactive=True)
    except Exception as e:
        FEW_SHOT_EXAMPLES = []
        return f"Error: {str(e)}", gr.File(value=None), gr.Button("Load Examples", variant="primary", size="sm", interactive=True)

def clear_few_shot_examples():
    """Clear uploaded few-shot examples - also remove any saved file"""
    global FEW_SHOT_EXAMPLES
    
    # Clear global variable
    FEW_SHOT_EXAMPLES = []
    
    # Remove the saved file
    try:
        if os.path.exists('few_shot_examples.json'):
            os.remove('few_shot_examples.json')
    except:
        pass
    
    # Remove any database-specific file if exists
    if CURRENT_DB:
        db_specific_file = f"few_shot_examples_{CURRENT_DB}.json"
        try:
            if os.path.exists(db_specific_file):
                os.remove(db_specific_file)
        except:
            pass
    
    return "Few-shot examples cleared", gr.File(value=None), gr.Button("Load Examples", variant="primary", size="sm", interactive=True)


def test_connection_wrapper(connection_method, auth_type, server, username, password, connection_string):
    """
    Wrapper for test connection that handles both methods
    """
    if connection_method == "Connection String":
        # Use connection string
        if not connection_string or not connection_string.strip():
            return "Please enter a connection string", gr.Dropdown(choices=[], interactive=False), gr.Button("Test Connection", variant="primary", interactive=True)
        return test_connection_and_get_dbs(connection_method, None, None, None, None, connection_string)
    else:
        # Use individual fields
        if not server or not server.strip():
            return "Please enter server name", gr.Dropdown(choices=[], interactive=False), gr.Button("Test Connection", variant="primary", interactive=True)
        return test_connection_and_get_dbs(connection_method, auth_type, server, username, password, None)

def toggle_connection_ui(is_connected):
    """Show/hide connection UI based on connection state"""
    if is_connected:
        # Hide connection UI, show New Connection button
        return (
            gr.Markdown(visible=False),      # "### Database Connection" title
            gr.Row(visible=False),           # Connection method selector row
            gr.Textbox(visible=False),       # Connection string input
            gr.Row(visible=False),           # Individual fields row
            gr.Row(visible=False),           # Server row
            gr.Row(visible=False),           # SQL auth row
            gr.Row(visible=False),           # entraid_auth_row - ADDED THIS LINE
            gr.Textbox(visible=False),       # Connection test result
            gr.Button(visible=False),        # Test Connection button
            gr.Button(visible=True, variant="primary", size="sm")  # New Connection button
        )
    else:
        # Show connection UI, hide New Connection button
        return (
            gr.Markdown(visible=True),       # "### Database Connection" title
            gr.Row(visible=True),            # Connection method selector row
            gr.Textbox(visible=False),       # Connection string (controlled by method)
            gr.Row(visible=True),            # Individual fields row
            gr.Row(visible=True),            # Server row
            gr.Row(visible=False),           # SQL auth row (default)
            gr.Row(visible=False),           # entraid_auth_row (default) - ADDED THIS LINE
            gr.Textbox(visible=True),        # Connection test result
            gr.Button(visible=True, variant="primary", interactive=True),  # Test Connection button
            gr.Button(visible=False)         # New Connection button
        )
    
    
def toggle_auth_fields(auth_type):
    """
    Show/hide credential fields based on selected authentication type
    """
    if auth_type == "SQL Server Authentication":
        return (
            gr.Row(visible=True),  # sql_auth_row
            gr.Row(visible=False), # entraid_auth_row
            gr.Textbox(interactive=True, label="Username"),  # username_input
            gr.Textbox(interactive=True, label="Password")   # password_input
        )
    else:
        # Windows Auth or other Entra methods without UI credentials
        return (
            gr.Row(visible=False),  # sql_auth_row
            gr.Row(visible=False),  # entraid_auth_row
            gr.Textbox(interactive=False, label="Username"),  # username_input
            gr.Textbox(interactive=False, label="Password")   # password_input
        )

def test_connection_and_get_dbs(connection_method, auth_type, server, username, password, connection_string):
    """
    Test connection and get available databases
    """
    global SERVER_NAME
    
    try:
        # Use connection string if provided
        if connection_method == "Connection String" and connection_string and connection_string.strip():
            success, message = test_connection(None, None, None, None, connection_string)
        else:
            # Use individual fields
            success, message = test_connection(auth_type, server, username, password, None)
        
        if not success:
            return message, gr.Dropdown(choices=[], interactive=False), gr.Button("Test Connection", variant="primary", interactive=True)
        
        # Get available databases
        databases = get_available_databases()
        
        if not databases:
            return f"{message}\nNo accessible databases found.", gr.Dropdown(choices=[], interactive=False), gr.Button("Test Connection", variant="primary", interactive=True)
        
        return f"Connected: {message}\nFound {len(databases)} databases.", gr.Dropdown(
            choices=databases, 
            value=None,
            label=f"Select Database ({len(databases)} found)",
            interactive=True
        ), gr.Button("Connected", variant="secondary", interactive=False)
        
    except Exception as e:
        return f"Error: {str(e)}", gr.Dropdown(choices=[], interactive=False), gr.Button("Test Connection", variant="primary", interactive=True)

def connect_db_wrapper(database_name):
    """
    Wrapper for connect_to_database
    """
    if not database_name or database_name == "No databases found":
        return "Please select a valid database", "### Connected Database: **Not Connected**"
    
    status = connect_to_database(database_name)
    return status, f"### Connected Database: **{database_name}**"

def update_db_connect_button(db_name):
    """
    Update database connect button state
    """
    global FEW_SHOT_EXAMPLES
    
    if db_name == CURRENT_DB and db_name is not None:
        return gr.Button("Connected", variant="secondary", interactive=False, size="sm")
    elif db_name and db_name != "No databases found" and SERVER_NAME:
        # Check if few-shot examples are loaded
        if len(FEW_SHOT_EXAMPLES) == 0:
            return gr.Button("Upload Examples First", variant="secondary", interactive=False, size="sm")
        else:
            return gr.Button("Connect Database", variant="primary", interactive=True, size="sm")
    else:
        return gr.Button("Connect Database", variant="secondary", interactive=False, size="sm")
def get_available_models():
    """Get list of available models from Ollama"""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            return model_names
        return []
    except Exception as e:
        print(f"Error getting models: {e}")
        return []

def refresh_models():
    """Refresh available models from Ollama"""
    models = get_available_models()
    if models:
        return gr.Dropdown(
            choices=models, 
            value=None, 
            label=f"Available Models ({len(models)} found)"
        )
    else:
        return gr.Dropdown(
            choices=["No models found"], 
            value=None, 
            label="Available Models (0 found)",
            interactive=False
        )

def connect_model(model_name):
    """Connect to selected model"""
    global LLM_MODEL
    if model_name:
        LLM_MODEL = model_name
        print(f"Model connected: {LLM_MODEL}")
        return f"Connected to {model_name}", gr.Button("Connected", variant="secondary", interactive=False, size="sm")
    else:
        return "Please select a model first", gr.Button("Connect Model", variant="primary", interactive=True, size="sm")

def update_model_connect_button(model_name):
    """Update model connect button state"""
    if model_name == LLM_MODEL and model_name is not None:
        return gr.Button("Connected", variant="secondary", interactive=False, size="sm")
    elif model_name:
        return gr.Button("Connect Model", variant="primary", interactive=True, size="sm")
    else:
        return gr.Button("Connect Model", variant="secondary", interactive=False, size="sm")

def update_model_display():
    """Update the model display text"""
    if LLM_MODEL:
        return f"### Selected Model: **{LLM_MODEL}**"
    return "### Selected Model: **Not Connected**"

def update_history_dropdown():
    if not CURRENT_DB:
        return gr.Dropdown(choices=[], value=None, label="Select Previous Query (No database connected)")
    
    db_history = [entry for entry in CHAT_HISTORY if entry.get('database') == CURRENT_DB]
    
    if not db_history:
        return gr.Dropdown(choices=[], value=None, label=f"Select Previous Query ({CURRENT_DB} - No queries yet)")
    
    choices = []
    for i, entry in enumerate(db_history, 1):
        question = entry['user_message']
        if len(question) > 50:
            question = question[:47] + "..."
        
        label = f"Q{i}: {question}"
        choices.append((label, i-1))
    
    return gr.Dropdown(choices=choices, value=None, label=f"Select Previous Query ({CURRENT_DB})")

def display_selected_history(selection_index):
    if selection_index is None or not CURRENT_DB:
        return "Select a query from history to view details...", "No reasoning available", gr.Button(visible=False)

    db_history = [entry for entry in CHAT_HISTORY if entry.get('database') == CURRENT_DB]
    
    if not db_history:
        return f"No queries found for {CURRENT_DB}", "No reasoning available", gr.Button(visible=False)
    
    if 0 <= selection_index < len(db_history):
        entry = db_history[selection_index]
        bot_response = entry['bot_response'] or "No response available"
        reasoning = entry.get('reasoning', 'No reasoning available')
        has_sql = entry.get('sql_query') is not None

        display_text = f"""
**Query:**  
{entry['user_message']}

**Response:**  
{bot_response}
"""
        # Show button only if SQL query exists
        if has_sql:
            return display_text, reasoning, gr.Button("Generate Visuals", variant="primary", visible=True, interactive=True)
        else:
            return display_text, reasoning, gr.Button(visible=False)
    
    return "Selected entry not found.", "No reasoning available", gr.Button(visible=False)

def regenerate_visuals_from_history(selection_index):
    """Re-run the SQL query from history and generate fresh visualizations"""
    if selection_index is None or not CURRENT_DB:
        return None, None, None, None
    
    db_history = [entry for entry in CHAT_HISTORY if entry.get('database') == CURRENT_DB]
    
    if not db_history or selection_index >= len(db_history):
        return None, None, None, None
    
    entry = db_history[selection_index]
    sql_query = entry.get('sql_query')
    
    if not sql_query:
        print("No SQL query found in history entry")
        return None, None, None, None
    
    try:
        print(f"Re-executing SQL from history: {sql_query[:100]}...")
        
        # Re-execute the query
        results = execute_safe_query(sql_query)
        
        if results.empty:
            print("Query returned no results")
            return None, None, None, None
        
        # Generate fresh visualizations
        visuals = generate_plotly_visualizations(results, target_charts=4)
        
        # Ensure exactly 4 charts
        while len(visuals) < 4:
            visuals.append(None)
        
        print(f"Generated {len([v for v in visuals if v is not None])} visualizations")
        return visuals[0], visuals[1], visuals[2], visuals[3]
        
    except Exception as e:
        print(f"Error regenerating visuals: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None
def chat_response(message):
    if not message or message.strip() == "":
        return "", pd.DataFrame(), "Please enter a question first.", None, None, None, None
    
    if not CURRENT_DB:
        return "Please connect to a database first.", pd.DataFrame(), "No database connected.", None, None, None, None
    
    if not LLM_MODEL:
        return "Please connect to a model first.", pd.DataFrame(), "No model connected.", None, None, None, None
    
    if not FEW_SHOT_EXAMPLES:
        return "Please upload few-shot examples before submitting queries.", pd.DataFrame(), "No examples loaded.", None, None, None, None
    
    # Get the query results
    summary, data, reasoning = get_dynamic_answer(message)
    
    # Generate visualizations
    visuals = []
    if data is not None and not data.empty:
        visuals = generate_plotly_visualizations(data, target_charts=4)
    
    # Ensure we have exactly 4 values (pad with None if needed)
    while len(visuals) < 4:
        visuals.append(None)
    
    # Return ALL 7 values
    return summary, data, reasoning or "No reasoning provided.", visuals[0], visuals[1], visuals[2], visuals[3]
def clear_all():
    return "", pd.DataFrame(), "Reasoning will appear here after query execution..."


def update_submit_button_state(message):
    """Update submit button state based on message, database, model, and examples"""
    if (message and message.strip() and 
        CURRENT_DB and 
        LLM_MODEL and 
        FEW_SHOT_EXAMPLES and len(FEW_SHOT_EXAMPLES) > 0):
        return gr.Button("Submit", variant="primary", interactive=True)
    else:
        return gr.Button("Submit", variant="secondary", interactive=False)

def update_message_interactivity():
    """Update message textbox interactivity based on database, model, and examples"""
    if (CURRENT_DB and 
        LLM_MODEL and 
        FEW_SHOT_EXAMPLES and len(FEW_SHOT_EXAMPLES) > 0):
        return gr.Textbox(
            interactive=True,
            placeholder="Type your question here..."
        )
    else:
        return gr.Textbox(
            interactive=False,
            placeholder="Please connect to database, model, and upload examples first..."
        )
def reset_ui_to_initial_state():
    """Reset everything to initial state when New Connection is clicked"""
    global CURRENT_DB, CURRENT_DB_ENGINE, LLM_MODEL, SERVER_NAME, CURRENT_AUTH_TYPE, CURRENT_USERNAME, CURRENT_PASSWORD, FEW_SHOT_EXAMPLES
    
    # Reset global variables
    CURRENT_DB = None
    CURRENT_DB_ENGINE = None
    LLM_MODEL = None
    SERVER_NAME = None
    CURRENT_AUTH_TYPE = None
    CURRENT_USERNAME = None
    CURRENT_PASSWORD = None
    FEW_SHOT_EXAMPLES = []
    
    return (
        "No database connected",
        "### Connected Database: **Not Connected**",
        "",
        gr.Dropdown(choices=[], interactive=False, label="Available Databases", value=None),
        gr.Button("Connect Database", variant="secondary", interactive=False, size="sm"),
        gr.Button("Submit", variant="secondary", interactive=False),
        gr.Textbox(interactive=False, placeholder="Please connect to database, model, and upload examples first..."),
        "",
        pd.DataFrame(),
        "",
        "No model selected",
        gr.Button("Connect Model", variant="primary", interactive=True, size="sm"),
        "### Selected Model: **Not Connected**",
        gr.Dropdown(choices=[], label="Select Previous Query (No database connected)"),
        gr.Dropdown(choices=get_available_models(), value=None, label="Select Model"),
        "No examples loaded (required)",
        gr.File(value=None),
        gr.Button("Load Examples", variant="primary", size="sm", interactive=True),
        "Connect to a database first",  # ADD THIS LINE
        gr.Button("Refresh Schema", variant="secondary", interactive=False, size="sm")  # ADD THIS LINE
    )
def refresh_ui_after_query():
    """Refresh submit button and text field after query is answered"""
    if CURRENT_DB and LLM_MODEL:
        return (
            gr.Button("Submit", variant="primary", interactive=True),
            gr.Textbox(interactive=True, placeholder="Type your next question here...", value="")
        )
    else:
        return (
            gr.Button("Submit", variant="secondary", interactive=False),
            gr.Textbox(interactive=False, placeholder="Please connect to both a database and model first...")
        )
def refresh_databases():
            """Dynamically get available databases from SQL Server"""
            databases = get_available_databases()
            if databases:
                return gr.Dropdown(
                    choices=databases, 
                    value=None, 
                    label=f"Available Databases ({len(databases)} found)"
                )
            else:
                return gr.Dropdown(
                    choices=["No databases found"], 
                    value=None, 
                    label="Available Databases (0 found)",
                    interactive=False
                )    

def create_interface():
    with gr.Blocks(title="NL2SQLBot") as demo:   
        gr.Markdown("""
        # NL2SQLBot
        """)     
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Tabs():
                    with gr.TabItem("Connect server and model"):
                        db_connection_title = gr.Markdown("### Database Connection", visible=True)

                        with gr.Row(visible=True) as connection_method_row:
                            connection_method = gr.Radio(
                                choices=["Connection String", "Individual Fields"],
                                value="Connection String",
                                label="Connection Method",
                                interactive=True
                            )

                        with gr.Row(visible=True) as indivconnection_string:
                            connection_string_input = gr.Textbox(
                                label="Full Connection String",
                                placeholder="Server=servername;Database=master;Trusted_Connection=True;TrustServerCertificate=True",
                                lines=2,
                                interactive=True  # Should be interactive
                            )

                        # Individual fields - start with visible=False
                        with gr.Row(visible=False) as individual_fields_row:
                            auth_type = gr.Dropdown(
                                choices=[
                                    "Windows Authentication",
                                    "SQL Server Authentication", 
                                ],
                                value="Windows Authentication",
                                label="Authentication Type",
                                interactive=True
                            )

                        with gr.Row(visible=False) as server_row:  # Start hidden
                            server_input = gr.Textbox(
                                label="Server Name",
                                placeholder="server name or localhost\\SQLEXPRESS",
                                lines=1,
                                interactive=True
                            )
                                    
                        # Credentials section
                        with gr.Row(visible=False) as sql_auth_row:
                            username_input = gr.Textbox(
                                label="Username",
                                placeholder="SQL Server username",
                                lines=1,
                                interactive=False
                            )
                            password_input = gr.Textbox(
                                label="Password",
                                placeholder="SQL Server password",
                                type="password",
                                lines=1,
                                interactive=False
                            )
                        
                        with gr.Row(visible=False) as entraid_auth_row:
                            entraid_username_input = gr.Textbox(
                                label="Entra ID Username",
                                placeholder="user@company.com",
                                lines=1,
                                interactive=False
                            )
                            entraid_password_input = gr.Textbox(
                                label="Entra ID Password",
                                type="password",
                                lines=1,
                                interactive=False
                            )
                        with gr.Row():
                            # Connection test result
                            conn_test_result = gr.Textbox(
                                label="Connection Test Result",
                                interactive=False,
                                lines=2,
                                visible=True
                            )
                            
                            # Test Connection button
                            test_conn_btn = gr.Button("Test Connection", variant="primary", visible=True)
                            
                        
                        new_connection_btn = gr.Button(
                            "New Connection", 
                            variant="primary", 
                            size="sm", 
                            visible=False  # Start hidden
                        )
                        gr.Markdown("### LLM Model")
                        with gr.Row():
                            model_dropdown = gr.Dropdown(
                                choices=[],
                                label="Select Model",
                                value=None,
                                interactive=True
                            )
                            model_status = gr.Textbox(
                            label="Model Status",
                            value="No model selected",
                            interactive=False
                            )
                        model_connect_btn = gr.Button("Connect Model", variant="primary", size="sm")
                    with gr.TabItem("Connect database"):    
                        gr.Markdown("### Select Database")
                        with gr.Row():
                            db_dropdown = gr.Dropdown(
                                choices=[],
                                label="Available Databases",
                                value=None,
                                interactive=False
                            )
                            connection_status = gr.Textbox(
                            label="Connection Status(first time connection may take a while)",
                            value="No database connected",
                            interactive=False,
                            lines=2
                            )
                    
                        
                        
                        
                        gr.Markdown("### Choose a database from dropdown first")           
                        with gr.Row():
                            
                                few_shot_file = gr.File(
                                    label="Upload Few-Shot Examples JSON",
                                    file_types=[".json"],
                                    type="filepath",
                                    interactive=False  
                                )
                                gr.Markdown("""
                                        **Expected JSON format:**
                                        ```json
                                        {
                                        "few_shot_examples": [
                                            {
                                            "question": "top 5 products by sales",
                                            "sql": "SELECT TOP 5 p.ProductName, SUM(s.Amount) FROM Sales s JOIN Products p ON s.ProductID = p.ProductID GROUP BY p.ProductName ORDER BY SUM(s.Amount) DESC;"
                                            }
                                        ]
                                        }
                                        ```
                                    """)        
                        few_shot_status = gr.Textbox(
                                        label="Upload Status",
                                        value="No examples loaded",
                                        interactive=False,
                                        lines=1,
                                        
                                    )
                        with gr.Row():
                                    
                                    
                                    upload_examples_btn = gr.Button("Load Examples", variant="secondary", size="sm", interactive=False)
                                        
                                    clear_examples_btn = gr.Button("Clear Examples", variant="secondary", size="sm")

                        connect_btn = gr.Button("Connect Database", variant="primary", size="sm", interactive=False)
                        gr.Markdown("### Schema Management")
                        refresh_schema_status = gr.Textbox(
                            label="Schema Status",
                            value="Connect to a database first",
                            interactive=False,
                            lines=2
                        )
                        refresh_schema_btn = gr.Button("Refresh Schema", variant="secondary", size="sm", interactive=False)
                                                
                                                    
                                    
                
            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.TabItem("New Query"):
                        with gr.Row():
                            current_model_display = gr.Markdown(
                                value="### Selected Model: **Not Connected**"
                            )
                            current_db_display = gr.Markdown(                 
                                value="### Connected Database: **Not Connected**"                
                            )
                        gr.Markdown("---")
                    
                        
                        gr.Markdown("### Ask a Question")
                        msg = gr.Textbox(
                            label="Your Question",
                            placeholder="Please connect to both a database and model first...",
                            lines=2,
                            interactive=False
                        )
                        with gr.Row():
                            submit_btn = gr.Button("Submit", variant="primary", interactive=False)
                            clear_btn = gr.Button("Clear", variant="secondary")
                        
                        # Results Section
                        gr.Markdown("### Results Summary")
                        output = gr.Textbox(
                            label="Summary",
                            interactive=False,
                            lines=4
                        )
                        
                

                        gr.Markdown("### Reasoning")
                        Reason = gr.Textbox(
                            label="Reason",
                            interactive=False,
                            lines=4
                        )

                        with gr.Tabs():
                            with gr.TabItem("Table View"):
                                data_output = gr.Dataframe(
                                    label="Data Table",
                                    interactive=False,
                                    wrap=True
                                )
                            
                            with gr.TabItem("Auto Visualizations"):
                                with gr.Row():
                                    chart_1 = gr.Plot(label="Chart 1")
                                    chart_2 = gr.Plot(label="Chart 2")
                                with gr.Row():
                                    chart_3 = gr.Plot(label="Chart 3")
                                    chart_4 = gr.Plot(label="Chart 4")
                            
                        

                       
                    with gr.TabItem("Query History"):
                        history_dropdown = gr.Dropdown(
                            choices=[],
                            label="Select Previous Query",
                            interactive=True,
                            allow_custom_value=False
                        )
                        history_display = gr.Markdown(
                            value="Select a query from history to view details..."
                        )
                        
                       
                        
                        
                    
                        gr.Markdown("### Query Reasoning")
                        reasoning_display = gr.Markdown(
                            value="Reasoning will appear here after query execution..."
                        )

                        regenerate_visuals_btn = gr.Button(
                            "Generate Visuals", 
                            variant="primary", 
                            visible=False  
                        )
                        
                        # ADD THIS: Visual outputs in history tab
                        gr.Markdown("### Generated Visualizations")
                        with gr.Row():
                            history_chart_1 = gr.Plot(label="Chart 1")
                            history_chart_2 = gr.Plot(label="Chart 2")
                        with gr.Row():
                            history_chart_3 = gr.Plot(label="Chart 3")
                            history_chart_4 = gr.Plot(label="Chart 4")
                            
        # ====== EVENT HANDLERS ======
        
        upload_examples_btn.click(
                    fn=upload_few_shot_examples,
            inputs=[few_shot_file],
            outputs=[few_shot_status, few_shot_file, upload_examples_btn]
        ).then(
            fn=update_db_connect_button,
            inputs=[db_dropdown],
            outputs=[connect_btn]
        ).then(
            fn=update_submit_button_state,
            inputs=[msg],
            outputs=[submit_btn]
        )
        clear_examples_btn.click(
            fn=clear_few_shot_examples,
            outputs=[few_shot_status, few_shot_file, upload_examples_btn]
        ).then(
            fn=update_db_connect_button,
            inputs=[db_dropdown],
            outputs=[connect_btn]
        ).then(
            fn=update_submit_button_state,
            inputs=[msg],
            outputs=[submit_btn]
        )
        test_conn_btn.click(
            fn=test_connection_wrapper,  # Your existing wrapper function
            inputs=[
                connection_method,
                auth_type,
                server_input,
                username_input,
                password_input,
                connection_string_input
            ],
            outputs=[conn_test_result, db_dropdown, test_conn_btn]
        ).then(
            # Check if button says "Connected" - then toggle UI
            fn=lambda btn_text: toggle_connection_ui(btn_text == "Connected"),
           
            inputs=[test_conn_btn],
            outputs=[
                db_connection_title,
                connection_method_row,
                connection_string_input,
                individual_fields_row,
                server_row,
                sql_auth_row,
                entraid_auth_row,
                conn_test_result,
                test_conn_btn,
                new_connection_btn
            ]
        ).then(
            fn=update_db_connect_button,
            inputs=[db_dropdown],
            outputs=[connect_btn]
        )

        
        new_connection_btn.click(
            fn=lambda: toggle_connection_ui(False),
            outputs=[
                db_connection_title,
                connection_method_row,
                connection_string_input,
                individual_fields_row,
                server_row,
                sql_auth_row,
                entraid_auth_row,
                conn_test_result,
                test_conn_btn,
                new_connection_btn
            ]
        ).then(
            fn=reset_ui_to_initial_state,
            outputs=[
                connection_status,
                current_db_display,
                conn_test_result,
                db_dropdown,
                connect_btn,
                submit_btn,
                msg,
                output,
                data_output,
                Reason,
                model_status,
                model_connect_btn,
                current_model_display,
                history_dropdown,
                model_dropdown,
                few_shot_status,
                few_shot_file,
                upload_examples_btn,
                refresh_schema_status,
                refresh_schema_btn
            ]
        ).then(
            fn=initialize_connection_ui,
            outputs=[
                indivconnection_string,
                individual_fields_row,
                server_row,
                sql_auth_row,
                entraid_auth_row,
                auth_type,
                server_input,
                username_input,
                password_input,
                entraid_username_input,
                entraid_password_input
            ]
        ).then(
            # Don't need separate clear_query_interface here because reset_ui_to_initial_state already clears everything
            fn=lambda: (
                "Select a query from history to view details...", 
                "No reasoning available", 
                None, None, None, None
            ),
            outputs=[
                history_display, 
                reasoning_display, 
                history_chart_1, 
                history_chart_2, 
                history_chart_3, 
                history_chart_4
            ]
        )
    
        connection_method.change(
            fn=toggle_connection_method,
            inputs=[connection_method],
            outputs=[
                indivconnection_string,  # Changed from connection_string_input
                individual_fields_row,
                server_row,
                sql_auth_row,
                entraid_auth_row,
                auth_type,
                server_input,
                username_input,
                password_input,
                entraid_username_input,
                entraid_password_input
            ]
        )
        
        # Auth type change handler
        auth_type.change(
            fn=toggle_auth_fields,
            inputs=[auth_type],
            outputs=[sql_auth_row, entraid_auth_row, username_input, password_input]
        )
        
       
        db_dropdown.change(
            fn=update_db_connect_button,
            inputs=[db_dropdown],
            outputs=[connect_btn]
        ).then(
            fn=lambda x: "### Connected Database: **Not Connected**",
            outputs=[current_db_display]
        ).then(
           
            fn=refresh_few_shot_on_database_change,
            inputs=[db_dropdown],
            outputs=[few_shot_status, few_shot_file, upload_examples_btn]
        ).then(
             fn=update_upload_button_state, 
             inputs=[db_dropdown],           
             outputs=[upload_examples_btn,few_shot_file]   
        ).then(
            fn=update_submit_button_state,
            inputs=[msg],
            outputs=[submit_btn]
        ).then(
            fn=update_message_interactivity,
            outputs=[msg]
        ).then(
            fn=clear_query_interface,  # ADD THIS LINE - Clear the query interface
            outputs=[msg, output, data_output, Reason, chart_1, chart_2, chart_3, chart_4, submit_btn]
        ).then(
            fn=lambda: (
                "Select a query from history to view details...", 
                "No reasoning available", 
                None, None, None, None
            ),
            outputs=[
                history_display, 
                reasoning_display, 
                history_chart_1, 
                history_chart_2, 
                history_chart_3, 
                history_chart_4
            ]
        )
        
        connect_btn.click(
            fn=connect_db_wrapper,
            inputs=[db_dropdown],
            outputs=[connection_status, current_db_display]
        ).then(
            fn=initialize_connection_ui
        ).then(
            fn=update_history_dropdown,
            outputs=[history_dropdown]
        ).then(
            fn=update_db_connect_button,
            inputs=[db_dropdown],
            outputs=[connect_btn]
        ).then(
            fn=update_submit_button_state,
            inputs=[msg],
            outputs=[submit_btn]
        ).then(
            fn=update_message_interactivity,
            outputs=[msg]
        ).then(  # ADD THIS ENTIRE .then() BLOCK
            fn=lambda: ("Schema loaded successfully", gr.Button("Refresh Schema", variant="secondary", interactive=True)),
            outputs=[refresh_schema_status, refresh_schema_btn]
        ).then(
            fn=clear_query_interface,  # ADD THIS LINE - Clear query interface after connecting
            outputs=[msg, output, data_output, Reason, chart_1, chart_2, chart_3, chart_4, submit_btn]
        )

        refresh_schema_btn.click(
            fn=refresh_schema,
            outputs=[refresh_schema_status, refresh_schema_btn]
        )
                
        # Model dropdown change handler
        model_dropdown.change(
            fn=update_model_connect_button,
            inputs=[model_dropdown],
            outputs=[model_connect_btn]
        ).then(
            fn=lambda x: "### Selected Model: **Not Connected**",
            outputs=[current_model_display]
        ).then(
            fn=update_submit_button_state,
            inputs=[msg],
            outputs=[submit_btn]
        ).then(
            fn=update_message_interactivity,
            outputs=[msg]
        ).then(
            fn=clear_query_interface,  # ADD THIS LINE - Clear the query interface
            outputs=[msg, output, data_output, Reason, chart_1, chart_2, chart_3, chart_4, submit_btn]
        ).then(
            # ADD THIS NEW BLOCK TO CLEAR HISTORY
            fn=lambda: (
                "Select a query from history to view details...", 
                "No reasoning available", 
                None, None, None, None
            ),
            outputs=[
                history_display, 
                reasoning_display, 
                history_chart_1, 
                history_chart_2, 
                history_chart_3, 
                history_chart_4
            ]
        )

        
        # Model connect button handler
        model_connect_btn.click(
            fn=connect_model,
            inputs=[model_dropdown],
            outputs=[model_status, model_connect_btn]
        ).then(
            fn=update_model_display,
            outputs=[current_model_display]
        ).then(
            fn=update_submit_button_state,
            inputs=[msg],
            outputs=[submit_btn]
        ).then(
            fn=update_message_interactivity,
            outputs=[msg]
        ).then(
            fn=clear_query_interface,  # ADD THIS LINE - Clear query interface after connecting model
            outputs=[msg, output, data_output, Reason, chart_1, chart_2, chart_3, chart_4, submit_btn]
        )
        
        # Query input handlers
        msg.change(
            fn=update_submit_button_state,
            inputs=[msg],
            outputs=[submit_btn]
        )
        
        # Update the msg.submit handler:
        msg.submit(
            fn=chat_response,
            inputs=[msg],
            outputs=[output, data_output, Reason, chart_1, chart_2, chart_3, chart_4]  # Now 7 outputs
        ).then(
            fn=update_history_dropdown,
            outputs=[history_dropdown]
        ).then(
            fn=refresh_ui_after_query,
            outputs=[submit_btn, msg]
        )

        # Update the submit_btn.click handler:
        submit_btn.click(
            fn=chat_response,
            inputs=[msg],
            outputs=[output, data_output, Reason,chart_1, chart_2, chart_3, chart_4]
        ).then(
            fn=update_history_dropdown,
            outputs=[history_dropdown]
        ).then(
            fn=refresh_ui_after_query,
            outputs=[submit_btn, msg]
        )  
       
        
        clear_btn.click(
            fn=clear_all,
            outputs=[msg, data_output, Reason]
        ).then(
            fn=lambda: gr.Button("Submit", variant="secondary", interactive=False),
            outputs=[submit_btn]
        )
        
        history_dropdown.change(
            fn=display_selected_history,
            inputs=[history_dropdown],
            outputs=[history_display, reasoning_display, regenerate_visuals_btn]  # Added button
        ).then(
            fn=lambda: (None, None, None, None),  # Clear all charts when dropdown changes
            outputs=[history_chart_1, history_chart_2, history_chart_3, history_chart_4]
        )

        # ADD THIS: New event handler for button
        regenerate_visuals_btn.click(
            fn=regenerate_visuals_from_history,
            inputs=[history_dropdown],
            outputs=[history_chart_1, history_chart_2, history_chart_3, history_chart_4]
        )

        demo.load(
            fn=initialize_connection_ui,  # Add this first
            outputs=[
                indivconnection_string,
                individual_fields_row,
                server_row,
                sql_auth_row,
                entraid_auth_row,
                auth_type,
                server_input,
                username_input,
                password_input,
                entraid_username_input,
                entraid_password_input
            ]
        ).then(
            fn=refresh_models,
            outputs=[model_dropdown]
        ).then(
            fn=update_model_display,
            outputs=[current_model_display]
        ).then(
            fn=update_history_dropdown,
            outputs=[history_dropdown]
        ).then(
            fn=lambda: gr.Button("Submit", variant="secondary", interactive=False),
            outputs=[submit_btn]
        ).then(
            fn=update_message_interactivity,
            outputs=[msg]
        ).then(
            fn=update_upload_button_state,  # ADD THIS
            inputs=[db_dropdown],            # ADD THIS
            outputs=[upload_examples_btn, few_shot_file]    # ADD THIS
        )
        
    return demo

def refresh_few_shot_on_database_change(database_name):
    """
    When database changes, clear the uploaded file and examples
    User must re-upload for the new database
    """
    global FEW_SHOT_EXAMPLES
    
    # Clear the global examples
    FEW_SHOT_EXAMPLES = []
    
    # Clear any database-specific file
    if database_name and database_name != "No databases found":
        db_specific_file = f"few_shot_examples_{database_name}.json"
        try:
            if os.path.exists(db_specific_file):
                os.remove(db_specific_file)
        except:
            pass
    
    # Return cleared state
    return f"Please upload examples for {database_name}", None, gr.Button("Load Examples", variant="primary", size="sm", interactive=True)

def initialize_connection_ui():
    """
    Initialize the connection UI based on default connection method
    """
    default_method = "Connection String"  # Match your default
    
    if default_method == "Connection String":
        return (
            gr.Row(visible=True),      # indivconnection_string row
            gr.Row(visible=False),     # individual_fields_row
            gr.Row(visible=False),     # server_row
            gr.Row(visible=False),     # sql_auth_row
            gr.Row(visible=False),     # entraid_auth_row
            gr.Dropdown(interactive=False, value="Windows Authentication"),
            gr.Textbox(visible=False, interactive=False, label="Server Name", value=""),
            gr.Textbox(visible=False, interactive=False, label="Username", value=""),
            gr.Textbox(visible=False, interactive=False, label="Password", value=""),
            gr.Textbox(visible=False, interactive=False, label="Entra ID Username", value=""),
            gr.Textbox(visible=False, interactive=False, label="Entra ID Password", value="")
        )
    else:  # "Individual Fields"
        return (
            gr.Row(visible=False),     # indivconnection_string row
            gr.Row(visible=True),      # individual_fields_row
            gr.Row(visible=True),      # server_row
            gr.Row(visible=False),     # sql_auth_row (will be toggled by auth_type)
            gr.Row(visible=False),     # entraid_auth_row (will be toggled by auth_type)
            gr.Dropdown(interactive=True, value="Windows Authentication"),
            gr.Textbox(visible=True, interactive=True, label="Server Name", placeholder="server name or localhost\\SQLEXPRESS"),
            gr.Textbox(visible=False, interactive=False, label="Username", value=""),
            gr.Textbox(visible=False, interactive=False, label="Password", value=""),
            gr.Textbox(visible=False, interactive=False, label="Entra ID Username", value=""),
            gr.Textbox(visible=False, interactive=False, label="Entra ID Password", value="")
        )

def test_database_connection(database_name):
    """
    Test if we can connect to a specific database
    """
    global SERVER_NAME, CURRENT_AUTH_TYPE, CURRENT_USERNAME, CURRENT_PASSWORD
    
    try:
        engine = get_engine_from_connection(CURRENT_AUTH_TYPE, SERVER_NAME, database_name, CURRENT_USERNAME, CURRENT_PASSWORD)
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        print(f"Server connection successful: {database_name}")
        return True, engine
        
    except Exception as e:
        error_msg = f"Connection failed: {str(e)}"
        print(f"Server connection failed for {database_name}: {e}")
        return False, error_msg

def toggle_connection_method(method):
    """
    Toggle between connection string and individual fields
    """
    if method == "Connection String":
        return (
            gr.Row(visible=True),      # indivconnection_string row
            gr.Row(visible=False),     # individual_fields_row
            gr.Row(visible=False),     # server_row
            gr.Row(visible=False),     # sql_auth_row
            gr.Row(visible=False),     # entraid_auth_row
            gr.Dropdown(interactive=False, value="Windows Authentication"),
            gr.Textbox(visible=False, interactive=False, label="Server Name", value=""),
            gr.Textbox(visible=False, interactive=False, label="Username", value=""),
            gr.Textbox(visible=False, interactive=False, label="Password", value=""),
            gr.Textbox(visible=False, interactive=False, label="Entra ID Username", value=""),
            gr.Textbox(visible=False, interactive=False, label="Entra ID Password", value="")
        )
    else:  # "Individual Fields"
        return (
            gr.Row(visible=False),     # indivconnection_string row
            gr.Row(visible=True),      # individual_fields_row
            gr.Row(visible=True),      # server_row
            gr.Row(visible=False),     # sql_auth_row (will be toggled by auth_type)
            gr.Row(visible=False),     # entraid_auth_row (will be toggled by auth_type)
            gr.Dropdown(interactive=True, value="Windows Authentication"),
            gr.Textbox(visible=True, interactive=True, label="Server Name", placeholder="server name or localhost\\SQLEXPRESS"),
            gr.Textbox(visible=False, interactive=False, label="Username", value=""),
            gr.Textbox(visible=False, interactive=False, label="Password", value=""),
            gr.Textbox(visible=False, interactive=False, label="Entra ID Username", value=""),
            gr.Textbox(visible=False, interactive=False, label="Entra ID Password", value="")
        )
def refresh_schema():
    """
    Check if schema has been updated and refresh if necessary
    """
    global CURRENT_DB, CURRENT_DB_ENGINE, SCHEMA_INFO, VECTOR_DB
    
    if not CURRENT_DB or not CURRENT_DB_ENGINE:
        return "No database connected", gr.Button("Refresh Schema", variant="secondary", interactive=False)
    
    try:
        print(f"\n{'='*60}")
        print(f"Checking schema for updates: {CURRENT_DB}")
        print(f"{'='*60}")
        
        # Check schema status
        schema_info, cache_status = load_schema_with_validation(CURRENT_DB, CURRENT_DB_ENGINE)
        
        if cache_status == "VALID":
            # Schema is up to date
            status_msg = f"""✓ Schema is up-to-date for {CURRENT_DB}
- No changes detected
- Vector database is current
- Cache age: Valid"""
            print("Schema check: No updates needed")
            return status_msg, gr.Button("Refresh Schema", variant="secondary", interactive=True)
        
        else:
            # Schema needs refresh
            print(f"Schema refresh needed (Reason: {cache_status})")
            
            # Extract fresh schema
            new_schema_info = get_database_schema(CURRENT_DB_ENGINE, CURRENT_DB)
            
            if not new_schema_info or not new_schema_info.get('objects'):
                return f"Error: Could not extract schema for {CURRENT_DB}", gr.Button("Refresh Schema", variant="secondary", interactive=True)
            
            # Save updated schema
            db_last_modified = get_database_last_modified(CURRENT_DB_ENGINE)
            save_schema_with_metadata(new_schema_info, CURRENT_DB, db_last_modified)
            
            # Update global schema
            SCHEMA_INFO = new_schema_info
            
            # Recreate vector database
            print("Recreating vector database...")
            new_vector_db = create_or_load_vector_db(new_schema_info, CURRENT_DB, force_recreate=True)
            
            if not new_vector_db:
                return f"Warning: Schema updated but vector DB creation failed", gr.Button("Refresh Schema", variant="secondary", interactive=True)
            
            VECTOR_DB = new_vector_db
            
            status_msg = f"""✓ Schema refreshed successfully for {CURRENT_DB}
- Reason: {cache_status}
- Tables: {len(new_schema_info['objects'])}
- Relationships: {len(new_schema_info['relationships'])}
- Vector database: Rebuilt"""
            
            print("Schema refresh completed successfully")
            return status_msg, gr.Button("Refresh Schema", variant="secondary", interactive=True)
        
    except Exception as e:
        error_msg = f"Error refreshing schema: {str(e)}"
        print(f"Schema refresh error: {e}")
        import traceback
        traceback.print_exc()
        return error_msg, gr.Button("Refresh Schema", variant="secondary", interactive=True)
def clear_query_interface():
    """
    Clear only the query interface components when DB/Model changes or New Connection clicked
    """
    return (
        "",  # Clear message textbox
        "",  # Clear output summary
        pd.DataFrame(),  # Clear data table
        "Reasoning will appear here after query execution...",  # Reset reasoning
        None, None, None, None,  # Clear all 4 charts
        gr.Button("Submit", variant="secondary", interactive=False),  # Reset submit button
    )    
if __name__ == "__main__":
    # Initialize global variables
    SERVER_NAME = None
    CURRENT_DB = None
    CURRENT_DB_ENGINE = None
    LLM_MODEL = None
    AVAILABLE_MODELS = get_available_models()
    CHAT_HISTORY = load_chat_history()    
    
    
    print(f"Available LLM Models: {AVAILABLE_MODELS}")
    print(f"Selected LLM Model: {LLM_MODEL or 'None'}")
    print(f"Connected Database: {CURRENT_DB or 'None'}")
    print(f"Chat history loaded: {len(CHAT_HISTORY)} messages")
    print(f"SQLGlot available: {SQLGLOT_AVAILABLE}")
    print("\nStarting NL2SQLBot with flexible connection options...")
    
    demo = create_interface()
    demo.launch(share=False)
