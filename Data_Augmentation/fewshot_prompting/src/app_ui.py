import os
import webbrowser
import re
from threading import Timer
from flask import Flask, render_template, request, jsonify, Response
from langchain_core.prompts import PromptTemplate, FewShotPromptTemplate
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
    """
    Logs the LLM response to a separate file for CSV queries.
    If the response contains a 'Final Response:' section, only that part is logged.
    """
    log_text = response
    # Attempt to extract 'Final Response:' if present, for structured outputs
    if "# Final Response" in response:
        match = re.search(r'# Final Response\s*\n(.*?)(?=\n#|\Z)', response, re.DOTALL | re.IGNORECASE)
        if match:
            log_text = match.group(1).strip()
    elif "Final Response:" in response: # Legacy fallback for older reflection prompts
        try:
            log_text = response.split("Final Response:")[1].strip()
        except IndexError:
            log_text = response
    elif "Final Answer:" in response: # Even older legacy fallback
        try:
            log_text = response.split("Final Answer:")[1].strip()
        except IndexError:
            log_text = response

    with open(CSV_RESPONSE_LOG_FILE, "a") as f:
        f.write(log_text + "\n[[---]]\n")

def _assemble_prompt(loaded_components, examples, user_query):
    """
    Assembles the final prompt string from a list of component definitions,
    handling different component types and combining instructions/templates.
    """
    few_shot_string = ""
    instruction_block = []
    template_block = []
    final_query_string = ""

    for component_def in loaded_components:
        comp_type = component_def.get('_type')

        if comp_type == "few_shot":
            example_prompt = PromptTemplate(
                template=component_def["example_prompt"]["template"],
                input_variables=component_def["example_prompt"]["input_variables"]
            )
            few_shot_prompt = FewShotPromptTemplate(
                examples=examples,
                example_prompt=example_prompt,
                prefix=component_def["prefix"],
                suffix=component_def["suffix"],
                input_variables=[], # No input variables at this stage
                example_separator="\n\n"
            )
            few_shot_string = few_shot_prompt.format()

        elif comp_type == "component":
            if "instruction" in component_def:
                instruction_block.append(component_def["instruction"])
            if "template" in component_def:
                template_block.append(component_def["template"])

        elif comp_type == "final_query":
            final_query_template = PromptTemplate(
                template=component_def['template'],
                input_variables=["user_query"]
            )
            final_query_string = final_query_template.format(user_query=user_query)

        else:
            print(f"Warning: Unknown component type '{comp_type}' encountered.")

    # Assemble the final prompt string
    final_prompt_parts = []
    if few_shot_string:
        final_prompt_parts.append(few_shot_string)

    if instruction_block:
        final_prompt_parts.append("\n---\n# OVERALL INSTRUCTIONS\n" + "\n".join(instruction_block))

    if template_block:
        final_prompt_parts.append("\n---\n# REQUIRED OUTPUT STRUCTURE\n" + "\n".join(template_block))

    if final_query_string:
        final_prompt_parts.append("\n" + final_query_string) # Add a newline for separation

    return "\n".join(final_prompt_parts)

def run_cli(context: dict):
    """Runs the command-line interface."""
    mode = context.get("mode")
    print("\n--- Conversation Start ---")
    print("Type 'quit' or 'exit' to end the conversation.")
    print("To query with a file, use: file_query: /path/to/your/file.txt")
    print("To use batch query mode, type: csv_query")

    history = InMemoryHistory()

    while True:
        try:
            user_input = prompt("> ", history=history, multiline=False).strip()
        except EOFError:
            break

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
            try:
                input_df = pd.read_csv(io.StringIO(csv_text))
                if 'file_name' not in input_df.columns:
                    print("Error: 'file_name' column is required in CSV data.")
                    continue

                def aggregate_rows(group):
                    other_cols_df = group.drop(columns='file_name')
                    col_names = ' '.join(other_cols_df.columns)
                    rows_as_str = '\n'.join(other_cols_df.apply(lambda row: ' '.join(row.astype(str)), axis=1))
                    return f"{col_names}\n{rows_as_str}"

                aggregated_inputs = input_df.groupby('file_name', sort=False).apply(aggregate_rows).reset_index(name='query')
                queries_to_process = aggregated_inputs['query'].tolist()

                print(f"\nFound {len(queries_to_process)} queries to process from CSV data.")

                for i, query in enumerate(queries_to_process):
                    print(f"\n--- Processing Query {i+1}/{len(queries_to_process)} ---")
                    if mode == 'conversational':
                        chain = context['chain']
                        full_response = ""
                        print("Model: ", end="", flush=True)
                        for chunk in chain.stream({"user_query": query}):
                            response_piece = chunk.get('text', '')
                            print(response_piece, end="", flush=True)
                            full_response += response_piece
                        print()
                        log_conversation(query, full_response)
                        log_csv_response(full_response)
                    else: # single_shot or dspy_single_shot
                        print("Model is thinking...")
                        current_mode = context.get("mode")
                        if current_mode == "dspy_single_shot":
                            dspy_program = context['dspy_program']
                            result = dspy_program(query=query)
                            response = result.response
                            print(f"Model: {response}")
                            log_conversation(query, response)
                            log_csv_response(response)
                        else: # original single_shot
                            llm = context['llm']
                            final_prompt = _assemble_prompt(context['prompt_components'], context['examples'], query)
                            response = llm.invoke(final_prompt)
                            print(f"Model: {response}")
                            log_conversation(query, response)
                            log_csv_response(response)

            except Exception as e:
                print(f"Error processing CSV data: {e}")
            continue

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

        current_mode = context.get("mode")
        if current_mode == 'conversational':
            chain = context['chain']
            full_response = ""
            print("Model: ", end="", flush=True)
            for chunk in chain.stream({"user_query": query_to_send}):
                response_piece = chunk.get('text', '')
                print(response_piece, end="", flush=True)
                full_response += response_piece
            print()
            log_conversation(query_to_send, full_response)
        elif current_mode == "dspy_single_shot":
            print("Model is thinking... (DSPy)")
            dspy_program = context['dspy_program']
            result = dspy_program(query=query_to_send)
            response = result.response
            print(f"Model: {response}")
            log_conversation(query_to_send, response)
        else: # original single_shot
            print("Model is thinking...")
            llm = context['llm']
            final_prompt = _assemble_prompt(context['prompt_components'], context['examples'], query_to_send)
            print("\n--- Assembled Prompt ---\n")
            print(final_prompt)
            print("\n------------------------\n")
            response = llm.invoke(final_prompt)
            print(f"Model: {response}")
            log_conversation(query_to_send, response)

def run_web(context: dict, host: str, port: int):
    """Runs the web interface."""
    app = Flask(__name__, template_folder=os.path.abspath('templates'))

    @app.route('/query_stream')
    def query_stream():
        if context.get("mode") != 'conversational':
            return Response("data: Streaming is only available in conversational mode.\n\n", mimetype='text/event-stream')

        user_query = request.args.get('query', '')
        if not user_query:
            return Response("data: Query is required.\n\n", mimetype='text/event-stream')

        chain = context['chain']
        def generate():
            full_response = ""
            for chunk in chain.stream({"user_query": user_query}):
                response_piece = chunk.get('text', '')
                full_response += response_piece
                for line in response_piece.splitlines():
                    yield f"data: {line}\\n" # Send newline as a literal string
                yield "data: \n" # Use a single newline as a separator event for the client

        def log_after_stream(q, r):
            log_conversation(q, r)

        def new_generate():
            chain_response = chain.invoke({"user_query": user_query})
            response_text = chain_response.get('text', '') if isinstance(chain_response, dict) else str(chain_response)
            log_conversation(user_query, response_text)

            # stream the full response
            for char in response_text:
                if char == '\n':
                    yield "data: <br>\n\n" # Send <br> for newlines
                else:
                    yield f"data: {char}\n\n"

        def stream_and_log():
            full_response = ""
            # Stream response to client
            for chunk in chain.stream({"user_query": user_query}):
                response_piece = chunk.get('text', '')
                full_response += response_piece
                yield f"data: {response_piece.replacechr(10, '<br>')}\n\n"
            # Log after streaming is complete
            log_conversation(user_query, full_response)

        def generate_and_log_after():
            full_response = ""
            for chunk in chain.stream({"user_query": user_query}):
                response_piece = chunk.get('text', '')
                full_response += response_piece
                # Send data chunk by chunk
                yield f"data: {response_piece}\n\n"
            log_conversation(user_query, full_response)

        return Response(generate_and_log_after(), mimetype='text/event-stream')


    @app.route('/query_single_shot', methods=['POST'])
    def query_single_shot():
        current_mode = context.get("mode")
        if current_mode not in ["single_shot", "dspy_single_shot"]:
            return jsonify({"error": "This endpoint is for single-shot modes only."}), 400

        user_query = request.json.get('query')
        if not user_query:
            return jsonify({"error": "Query is required"}), 400

        if current_mode == "dspy_single_shot":
            try:
                dspy_program = context['dspy_program']
                result = dspy_program(query=user_query)
                response = result.response
                log_conversation(user_query, response)
                return jsonify({"response": response, "assembled_prompt": "[Prompt compiled by DSPy. Not available for display.]"})
            except Exception as e:
                return jsonify({"error": f"Error during DSPy execution: {str(e)}"}), 500
        else: # original single_shot
            try:
                llm = context['llm']
                final_prompt = _assemble_prompt(context['prompt_components'], context['examples'], user_query)
                response = llm.invoke(final_prompt)
                log_conversation(user_query, response)
                return jsonify({"response": response, "assembled_prompt": final_prompt})
            except Exception as e:
                return jsonify({"error": f"Error during LLM execution: {str(e)}"}), 500

    @app.route('/')
    def index():
        return render_template('index.html', mode=context.get("mode"))

    browser_host = host if host != '0.0.0.0' else '127.0.0.1'
    url = f"http://{browser_host}:{port}"
    Timer(1, lambda: webbrowser.open_new(url)).start()
    print(f"Starting web server at http://{host}:{port} (accessible at {url})")
    app.run(host=host, port=port)
