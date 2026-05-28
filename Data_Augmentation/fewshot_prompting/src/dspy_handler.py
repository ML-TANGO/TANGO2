import dspy
import os
import re
from dspy.teleprompt import BootstrapFewShot, BootstrapFewShotWithRandomSearch, MIPROv2
from src.ollama_manager import is_model_vlm
try:
    from bert_score import BERTScorer
except ImportError:
    BERTScorer = None

class GenerateResponse(dspy.Signature):
    """Generate a response based on a given query and optional image, following the provided examples."""

    query = dspy.InputField(desc="The user's query.")
    image = dspy.InputField(desc="Optional image input.", required=False)
    response = dspy.OutputField(desc="The generated response.")

class ConversationalSignature(dspy.Signature):
    """Given a chat history, a query, and an optional image, generate a response."""
    __doc__ = "Given a chat history, a query, and an optional image, generate a response."

    chat_history = dspy.InputField(desc="The past conversation history, as a string.")
    query = dspy.InputField(desc="The user's current query.")
    image = dspy.InputField(desc="Optional image input.", required=False)
    response = dspy.OutputField(desc="The model's response.")


# Global BERTScorer instance to avoid reloading the model
_bert_scorer = None

def get_bert_scorer():
    global _bert_scorer
    if _bert_scorer is None and BERTScorer is not None:
        # Using default English model (roberta-large)
        print("Initializing BERTScore model (this may take a moment)...")
        _bert_scorer = BERTScorer(lang="en", rescale_with_baseline=False)
    return _bert_scorer

def bert_score_metric(example, pred, trace=None):
    """
    A semantic similarity metric using BERTScore.
    Computes the F1 score between the reference and the prediction.
    """
    if not hasattr(pred, 'response') or not pred.response:
        return 0.0

    ref = getattr(example, 'response', '')
    hyp = pred.response

    if not ref:
        return 0.0

    scorer = get_bert_scorer()
    if scorer is None:
        # Fallback to Jaccard if BERTScore is not available
        return jaccard_metric(example, pred, trace)

    try:
        P, R, F1 = scorer.score([hyp], [ref], verbose=False)
        return F1.item()
    except Exception as e:
        print(f"BERTScore error: {e}")
        return 0.0

def jaccard_metric(example, pred, trace=None):
    """
    A simple Jaccard similarity metric for text generation.
    Returns a score between 0.0 and 1.0 based on word overlap.
    """
    if not hasattr(pred, 'response') or not pred.response:
        return 0.0

    gold_text = getattr(example, 'response', '')
    pred_text = pred.response

    if not gold_text:
        return 0.0

    gold_words = set(gold_text.lower().split())
    pred_words = set(pred_text.lower().split())

    if not gold_words:
        return 0.0

    intersection = gold_words.intersection(pred_words)
    union = gold_words.union(pred_words)

    return len(intersection) / len(union) if union else 0.0

def convert_examples(example_data, is_conversational=False):
    """
    Converts a list of dictionaries (from pandas) into a list of dspy.Example objects.
    Extracts images from query if present in '[image: path]' format.
    """
    dspy_examples = []
    image_pattern = r'\[image:\s*(.*?)\]'
    
    for eg in example_data:
        query_text = eg['query']
        # 이미지 태그 추출 및 텍스트 정제
        found_images = re.findall(image_pattern, query_text)
        clean_query = re.sub(image_pattern, '', query_text).strip()
        
        dspy_image = None
        if found_images:
            img_path = found_images[0].strip()
            if os.path.exists(img_path):
                try:
                    dspy_image = dspy.Image.from_file(img_path)
                except Exception as e:
                    print(f"Error loading image {img_path} for example: {e}")
        
        if is_conversational:
            example = dspy.Example(
                query=clean_query, 
                chat_history=eg.get('chat_history', ""), 
                image=dspy_image, 
                response=eg['response']
            )
            dspy_examples.append(example.with_inputs("query", "chat_history", "image"))
        else:
            example = dspy.Example(
                query=clean_query, 
                image=dspy_image, 
                response=eg['response']
            )
            dspy_examples.append(example.with_inputs("query", "image"))
    return dspy_examples

def compile_program(model_name, optimizer_name, examples, metric_name="bert_score", backend="ollama", backend_url="http://localhost:11434", max_bootstrapped_demos=6, is_conversational=False, mipro_auto_level='light'):
    """
    Configures the LLM and compiles a DSPy program using the specified optimizer.
    """
    # 1. Configure the LLM for DSPy
    if backend == 'vllm':
        print(f"--- DSPy Backend: vLLM ({backend_url}) ---")
        llm_client = dspy.LM(
            model=f"openai/{model_name}",
            api_base=backend_url,
            api_key="EMPTY"
        )
    else:
        print(f"--- DSPy Backend: Ollama ({backend_url}) ---")
        llm_client = dspy.LM(
            model=f"ollama_chat/{model_name}",
            api_base=backend_url
        )

    dspy.settings.configure(lm=llm_client)

    # 2. Convert pandas examples to dspy.Example
    trainset = convert_examples(examples, is_conversational=is_conversational)

    # [DEBUG] VLM 및 데이터 확인 (컴파일 단계에서만 출력)
    print("\n" + "-"*30)
    print(f"[DSPy Compilation Debug]")
    print(f" - Model: {model_name} ({backend.upper()})")
    
    # 통합 함수를 이용한 정밀한 VLM 여부 판단 (구조적 분석)
    vllm_model_path = None
    if backend == 'vllm':
        # main.py 또는 config에서 전달된 model_path 정보가 필요할 수 있으나,
        # 여기서는 model_name 자체가 경로일 수 있으므로 그대로 전달
        vllm_model_path = model_name 

    has_vision = is_model_vlm(
        model_name, 
        backend=backend, 
        backend_url=backend_url, 
        model_path=vllm_model_path
    )

    print(f" - Vision Component Detected: {'YES' if has_vision else 'NO (Text-only)'}")
    
    # 데이터셋 내 이미지 포함 여부 확인
    image_count = sum(1 for ex in trainset if getattr(ex, 'image', None) is not None)
    print(f" - Multimodal Data: Found {image_count} examples with images out of {len(trainset)} total.")
    
    if image_count > 0 and not has_vision:
        print(f" - WARNING: Multimodal data provided, but model architecture does not show vision support!")
    elif image_count > 0 and has_vision:
        print(f" - Status: VLM optimization mode ACTIVATED.")
    else:
        print(f" - Status: Text-only optimization mode.")
    print("-"*30 + "\n")

    # 3. Define the DSPy program based on mode
    if is_conversational:
        class ConversationalCoT(dspy.Module):
            def __init__(self):
                super().__init__()
                self.prog = dspy.ChainOfThought(ConversationalSignature)

            def forward(self, query, chat_history="", image=None):
                return self.prog(query=query, chat_history=chat_history, image=image)
        program_to_compile = ConversationalCoT()
    else:
        class CoT(dspy.Module):
            def __init__(self):
                super().__init__()
                self.prog = dspy.ChainOfThought(GenerateResponse)

            def forward(self, query, image=None):
                return self.prog(query=query, image=image)
        program_to_compile = CoT()


    # 4. Select Metric
    if metric_name == "jaccard":
        metric_fn = jaccard_metric
        print(f"--- DSPy Metric: Jaccard Similarity ---")
    else:
        metric_fn = bert_score_metric
        print(f"--- DSPy Metric: BERTScore (Semantic) ---")

    # 5. Select and configure the optimizer
    optimizer_map = {
        "BootstrapFewShot": BootstrapFewShot(metric=metric_fn, max_bootstrapped_demos=max_bootstrapped_demos),
        "BootstrapFewShotWithRandomSearch": BootstrapFewShotWithRandomSearch(metric=metric_fn, max_bootstrapped_demos=max_bootstrapped_demos, num_candidate_programs=10),
        "MIPROv2": MIPROv2(metric=metric_fn, max_bootstrapped_demos=max_bootstrapped_demos, auto=mipro_auto_level)
    }

    optimizer = optimizer_map.get(optimizer_name)
    if optimizer is None:
        raise ValueError(f"Unknown optimizer: {optimizer_name}. Available options are: {list(optimizer_map.keys())}")

    # 6. Compile the program
    compiled_program = optimizer.compile(
        student=program_to_compile,
        trainset=trainset
    )

    return compiled_program

def print_program_details(program):
    """
    Prints the few-shot examples (demos) and instructions of a compiled DSPy program.
    """
    print("\n" + "="*50)
    print("[DSPy Optimized Program Details]")
    print("="*50)

    try:
        predictors = list(program.named_predictors())

        if not predictors:
            print("⚠️  No predictors found in the program.")
            return

        for name, predictor in predictors:
            print(f"\nPredictor: {name} ({type(predictor).__name__})")

            # 1. Print Instructions
            instructions = None
            if hasattr(predictor, 'extended_signature'):
                instructions = getattr(predictor.extended_signature, 'instructions', None)

            if not instructions and hasattr(predictor, 'signature'):
                instructions = getattr(predictor.signature, 'instructions', None)

            if instructions:
                print("\n[Optimized Instructions]:")
                print(f"  {instructions}")
            else:
                print("  (Instructions not found)")

            # 2. Print Few-Shot Examples (Demos)
            demos = getattr(predictor, 'demos', [])

            if demos:
                print(f"\n[Selected Few-Shot Examples] (Count: {len(demos)}):")
                for i, demo in enumerate(demos):
                    print(f"\n  --- Example #{i+1} ---")
                    try:
                        demo_dict = demo.toDict() if hasattr(demo, 'toDict') else dict(demo)
                        for field_name, field_value in demo_dict.items():
                             print(f"  [{field_name.upper()}]: {field_value}")
                    except:
                        print(f"  {demo}")
            else:
                 print("  (No few-shot examples found in this predictor)")

    except Exception as e:
        print(f"\n⚠️  Error extracting details: {e}")
        # Debug: Print available attributes if extraction fails
        print(f"Debug - Program attributes: {dir(program)}")

    print("\n" + "="*50 + "\n")
