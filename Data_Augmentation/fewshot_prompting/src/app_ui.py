import os
import webbrowser
import re
from threading import Timer
from flask import Flask, render_template, request, jsonify, Response
from langchain_classic.chains import LLMChain
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
import pandas as pd
import io

LOG_FILE = "conversation.log"
CSV_RESPONSE_LOG_FILE = "csv_query_responses.log"

def log_conversation(query, response):
    """Logs the user query and model response to a file."""
    with open(LOG_FILE, "a") as f:
        f.write(f"User: {query}\n")
        f.write(f"Model: {response}\n")
        f.write("-" * 20 + "\n")

def log_csv_response(response):
    """Logs only the LLM response to a separate file for CSV queries."""
    with open(CSV_RESPONSE_LOG_FILE, "a") as f:
        f.write(response + "\n\n")

def run_cli(chain: LLMChain, mode: str):
    """Runs the command-line interface."""
    print("\n--- Conversation Start ---")
    print("Type 'quit' or 'exit' to end the conversation.")
    print("To query with a file, use: file_query: /path/to/your/file.txt")
    print("To use batch query mode, type: csv_query")

    history = InMemoryHistory()

    while True:
        try:
            user_input = prompt("> ", history=history, multiline=False).strip()
        except EOFError:
            break # Exit on Ctrl+D

        if user_input.lower() in ["quit", "exit"]:
            break
        
        if not user_input:
            continue

        if user_input.lower() == 'csv_query':
            print("--- CSV Batch Mode ---")
            print("Paste your CSV data below. Type 'END_CSV' on a new line to process.")
            csv_lines = []
            while True:
                line = prompt("csv> ", history=None, multiline=False)
                if line.strip().upper() == 'END_CSV':
                    break
                csv_lines.append(line)
            
            if not csv_lines:
                print("No CSV data entered.")
                continue

            csv_text = "\n".join(csv_lines)
            csv_file = io.StringIO(csv_text)

            try:
                input_df = pd.read_csv(csv_file)
                if 'file_name' not in input_df.columns:
                    print("Error: 'file_name' column is required in CSV data.")
                    continue

                def aggregate_rows(group):
                    other_cols_df = group.drop(columns='file_name')
                    # 컬럼명과 데이터를 포함
                    col_names = ' '.join(other_cols_df.columns)
                    rows_as_str = '\n'.join(other_cols_df.apply(lambda row: ' '.join(row.astype(str)), axis=1))
                    return f"{col_names}\n{rows_as_str}"

                aggregated_inputs = input_df.groupby('file_name', sort=False).apply(aggregate_rows).reset_index(name='query')
                queries_to_process = aggregated_inputs['query'].tolist()

                print(f"\nFound {len(queries_to_process)} queries to process from CSV data.")

                for i, query in enumerate(queries_to_process):
                    print(f"\n--- Processing Query {i+1}/{len(queries_to_process)} ---")
                    if mode == 'conversational':
                        full_response = ""
                        print("Model: ", end="", flush=True)
                        for chunk in chain.stream({"user_query": query}):
                            response_piece = chunk.get('text', '')
                            print(response_piece, end="", flush=True)
                            full_response += response_piece
                        print()
                        log_conversation(query, full_response)
                        log_csv_response(full_response)
                    else: # single_shot
                        print("Model is thinking...")
                        response = chain.invoke({"user_query": query})
                        final_response = response.get('text', 'Error: No response text found')
                        print(f"Model: {final_response}")
                        log_conversation(query, final_response)
                        log_csv_response(final_response)

            except Exception as e:
                print(f"Error processing CSV data: {e}")
            continue # Go back to main prompt

        # --- Standard single query and file_query logic ---
        query_to_send = ""
        if user_input.startswith("file_query:"):
            file_path = user_input.replace("file_query:", "").strip()
            if not os.path.exists(file_path):
                print(f"Error: File not found at '{file_path}'")
                continue
            try:
                with open(file_path, 'r') as f:
                    query_to_send = f.read()
                print(f"Querying with content from '{file_path}'...")
            except Exception as e:
                print(f"Error reading file: {e}")
                continue
        else:
            query_to_send = user_input

        if mode == 'conversational':
            full_response = ""
            print("Model: ", end="", flush=True)
            for chunk in chain.stream({"user_query": query_to_send}):
                response_piece = chunk.get('text', '')
                print(response_piece, end="", flush=True)
                full_response += response_piece
            print()
            log_conversation(query_to_send, full_response)
        else: # single_shot
            print("Model is thinking...")
            response = chain.invoke({"user_query": query_to_send})
            final_response = response.get('text', 'Error: No response text found')
            print(f"Model: {final_response}")
            log_conversation(query_to_send, final_response)

def run_web(chain: LLMChain, mode: str, host: str, port: int):
    """Runs the web interface."""
    app = Flask(__name__, template_folder=os.path.abspath('templates'))

    @app.route('/query_stream')
    def query_stream():
        user_query = request.args.get('query', '')
        if not user_query:
            # EventSource does not handle error responses well, so we just close the stream.
            return Response("data: Query is required.\n\n", mimetype='text/event-stream')

        def generate():
            full_response = ""
            for chunk in chain.stream({"user_query": user_query}):
                response_piece = chunk.get('text', '')
                full_response += response_piece
                # Per SSE spec, send each line as a separate 'data:' field
                for line in response_piece.splitlines():
                    yield f"data: {line}\n"
                # After all lines, send a final blank line to signal end of message
                yield "\n"
            log_conversation(user_query, full_response)
        
        return Response(generate(), mimetype='text/event-stream')

    @app.route('/query_single_shot', methods=['POST'])
    def query_single_shot():
        user_query = request.json.get('query')
        if not user_query:
            return jsonify({"error": "Query is required"}), 400
        
        response = chain.invoke({"user_query": user_query})
        final_response = response.get('text', 'Error: No response text found')
        log_conversation(user_query, final_response)
        return jsonify({"response": final_response})

    @app.route('/')
    def index():
        # The main query function is removed, so we just render the template.
        return render_template('index.html', mode=mode)

    # 0.0.0.0은 브라우저에서 열 수 없으므로 127.0.0.1로 변경
    browser_host = host if host != '0.0.0.0' else '127.0.0.1'
    url = f"http://{browser_host}:{port}"
    Timer(1, lambda: webbrowser.open_new(url)).start()
    print(f"Starting web server at http://{host}:{port} (accessible at {url})")
    app.run(host=host, port=port)
