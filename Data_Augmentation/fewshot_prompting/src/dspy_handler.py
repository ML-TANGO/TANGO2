import dspy
from dspy.teleprompt import BootstrapFewShot, BootstrapFewShotWithRandomSearch, MIPROv2
try:
    from bert_score import BERTScorer
except ImportError:
    BERTScorer = None

class GenerateResponse(dspy.Signature):
    """Generate a response based on a given query, following the provided examples."""

    query = dspy.InputField(desc="The user's query.")
    response = dspy.OutputField(desc="The generated response.")

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

def convert_examples(example_data):
    """
    Converts a list of dictionaries (from pandas) into a list of dspy.Example objects.
    """
    dspy_examples = []
    for eg in example_data:
        # Assuming the keys from data_loader are 'query' and 'response'
        dspy_examples.append(dspy.Example(query=eg['query'], response=eg['response']).with_inputs("query"))
    return dspy_examples

def compile_program(model_name, optimizer_name, examples, metric_name="bert_score", max_bootstrapped_demos=4, max_labeled_demos=16):
    """
    Configures the LLM and compiles a DSPy program using the specified optimizer.
    """
    # 1. Configure the LLM for DSPy using LiteLLM's 'ollama_chat' provider
    # The model name requires the 'ollama_chat/' prefix to be routed correctly by litellm.
    llm_client = dspy.LM(
        model=f"ollama_chat/{model_name}",
        api_base="http://localhost:11434"
    )
    dspy.settings.configure(lm=llm_client)

    # 2. Convert pandas examples to dspy.Example
    trainset = convert_examples(examples)

    # 3. Define the DSPy program
    class CoT(dspy.Module):
        def __init__(self):
            super().__init__()
            self.prog = dspy.ChainOfThought(GenerateResponse)

        def forward(self, query):
            return self.prog(query=query)

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
        "MIPROv2": MIPROv2(metric=metric_fn, max_bootstrapped_demos=max_bootstrapped_demos, init_temperature=1.0)
    }

    optimizer = optimizer_map.get(optimizer_name)
    if optimizer is None:
        raise ValueError(f"Unknown optimizer: {optimizer_name}. Available options are: {list(optimizer_map.keys())}")

    # 6. Compile the program
    compiled_program = optimizer.compile(
        student=CoT(),
        trainset=trainset
    )

    return compiled_program

def print_program_details(program):
    """
    Prints the few-shot examples (demos) and instructions of a compiled DSPy program.
    """
    print("\n" + "="*50)
    print("🔍 [DSPy Optimized Program Details]")
    print("="*50)

    try:
        predictors = list(program.named_predictors())

        if not predictors:
            print("⚠️  No predictors found in the program.")
            return

        for name, predictor in predictors:
            print(f"\n👉 Predictor: {name} ({type(predictor).__name__})")

            # 1. Print Instructions
            instructions = None
            if hasattr(predictor, 'extended_signature'):
                instructions = getattr(predictor.extended_signature, 'instructions', None)

            if not instructions and hasattr(predictor, 'signature'):
                instructions = getattr(predictor.signature, 'instructions', None)

            if instructions:
                print("\n📝 [Optimized Instructions]:")
                print(f"  {instructions}")
            else:
                print("  (Instructions not found)")

            # 2. Print Few-Shot Examples (Demos)
            demos = getattr(predictor, 'demos', [])

            if demos:
                print(f"\n📚 [Selected Few-Shot Examples] (Count: {len(demos)}):")
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
