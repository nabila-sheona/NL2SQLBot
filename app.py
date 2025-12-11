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



#code under developement.


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
            fn=test_connection_and_get_dbs,  # Your existing wrapper function
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
            fn=initialize_connection_ui
           
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
        ).then( fn=reset_database_connection,  # Add this first to reset variables
            inputs=[],
            outputs=[]
        ).then( fn=reset_model_connection,  # Add this first to reset variables
            inputs=[],
            outputs=[]
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
        ).then( fn=reset_database_connection,  # Add this first to reset variables
            inputs=[],
            outputs=[]
        ).then( fn=reset_model_connection,  # Add this first to reset variables
            inputs=[],
            outputs=[]
        )
    
        
        # Auth type change handler
        auth_type.change(
            fn=toggle_auth_fields,
            inputs=[auth_type],
            outputs=[sql_auth_row, entraid_auth_row, username_input, password_input]
        )
        
       
        db_dropdown.change(
            fn=reset_database_connection,  # Add this first to reset variables
            inputs=[],
            outputs=[]
        ).then(
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
            fn=reset_model_connection,  # Add this first to reset variables
            inputs=[],
            outputs=[]
            
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
            fn=reset_database_connection,  # Reset on page load
            inputs=[],
            outputs=[]
        ).then( fn=reset_model_connection,  # Add this first to reset variables
                inputs=[],
                outputs=[]   
        ).then(
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

if __name__ == "__main__":
    SERVER_NAME = None
    CURRENT_DB = None
    CURRENT_DB_ENGINE = None
    LLM_MODEL = None
    AVAILABLE_MODELS = get_available_models()
    CHAT_HISTORY = load_chat_history()    
   
    print(f"Available LLM Models: {AVAILABLE_MODELS}")
    print(f"Chat history loaded: {len(CHAT_HISTORY)} messages")
    print(f"SQLGlot available: {SQLGLOT_AVAILABLE}")
    print("\nStarting NL2SQLBot with flexible connection options...")
    
    demo = create_interface()
    demo.launch(share=False)

