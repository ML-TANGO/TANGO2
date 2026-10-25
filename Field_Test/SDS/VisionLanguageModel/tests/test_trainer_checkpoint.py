"""
Tests for VLMTrainer's per-checkpoint vlm_config.json write.

The method signature is `_save_checkpoint(self, model, trial)`, and HF Trainer
passes the WRAPPED model there. Under DeepSpeed that is a DeepSpeedEngine whose
`.config` is the DeepSpeed config dict, a real instance attribute that shadows
the engine's `__getattr__` forwarding. Reading the projector settings off that
argument therefore hands `vars()` a dict and raises TypeError at the first
save_steps, after a full model load and N training steps.

These tests pin that the config is taken from the unwrapped `self.model` and
that a non-VLMConfig is refused rather than crashing.

Run with an interpreter that has torch and pytest:
    /home/ywlee/miniforge3/envs/rag/bin/python -m pytest tests/test_trainer_checkpoint.py
"""
import ast
import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from model.config import VLMConfig


def save_checkpoint_source() -> str:
    """
    Source of VLMTrainer._save_checkpoint, read from the file.

    train.py imports transformers and peft at module scope, and the test
    interpreter has transformers but not peft, so the AST is the reliable way
    in.
    """
    tree = ast.parse(open(os.path.join(REPO_ROOT, "train.py"), encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_save_checkpoint":
            return ast.unparse(node)
    pytest.fail("VLMTrainer._save_checkpoint not found in train.py")


# ── What the checkpoint's model.safetensors carries ──────────────────────────
# VisionLanguageModelV2 is not a PreTrainedModel, so HF's Trainer._save writes
# the whole state dict to one safetensors file: the frozen CLIP and the frozen
# 8B LLM went into every checkpoint at 16.7 GB, while the projector-only phase
# had changed 78 MB. Measured on the server: one 3-step DeepSpeed run used
# 142 GB. VLMTrainer._save now keeps only what the run trained.


def trainer_method(name: str):
    """
    One method of VLMTrainer, pulled out of train.py by AST and left unbound.

    train.py imports transformers, peft and wandb at module scope. Extracting a
    single method keeps these tests independent of all three, and the methods
    only touch self.model, self.FROZEN_PREFIXES and print.
    """
    tree = ast.parse(open(os.path.join(REPO_ROOT, "train.py"), encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            namespace = {}
            exec(compile(ast.Module([node], []), "<train.py>", "exec"), namespace)
            return namespace[name]
    pytest.fail(f"VLMTrainer.{name} not found in train.py")


class FakeParam:
    def __init__(self, requires_grad, numel=4):
        self.requires_grad = requires_grad
        self._numel = numel

    def numel(self):
        return self._numel

    def element_size(self):
        return 2


class FakeTrainer:
    """The three attributes the extracted methods reach for."""

    FROZEN_PREFIXES = ("vision_encoder.", "language_model.")

    def __init__(self, trainable_keys, all_keys):
        self._params = {
            key: FakeParam(key in trainable_keys) for key in all_keys
        }

        class Model:
            def __init__(self, params):
                self._params = params

            def named_parameters(self):
                return list(self._params.items())

            def state_dict(self):
                return dict(self._params)

        self.model = Model(self._params)


PROJECTOR_KEYS = ["projector.proj.query", "projector.proj.out_proj.weight",
                  "projector.proj.arch_signature"]
FROZEN_KEYS = ["vision_encoder.model.embeddings.weight",
               "language_model.model.layers.0.self_attn.q_proj.weight",
               "language_model.model.embed_tokens.weight"]
LORA_KEYS = ["language_model.base_model.model.layers.0.self_attn.q_proj.lora_A.default.weight"]


def filter_with(trainable, keys):
    method = trainer_method("_trained_state_dict")
    trainer = FakeTrainer(trainable, keys)
    return method(trainer, trainer.model.state_dict())


def test_the_projector_phase_keeps_only_the_projector():
    keys = PROJECTOR_KEYS + FROZEN_KEYS
    # requires_grad is set on the projector's parameters; arch_signature is a
    # buffer and appears in neither named_parameters nor the trainable set.
    trainable = {"projector.proj.query", "projector.proj.out_proj.weight"}

    kept = filter_with(trainable, keys)

    assert set(kept) == set(PROJECTOR_KEYS)
    assert not any(k.startswith(("vision_encoder.", "language_model.")) for k in kept)


def test_the_projector_buffer_is_kept_even_though_it_is_not_trainable():
    """proj.arch_signature is what detects a num_heads mismatch on load."""
    kept = filter_with({"projector.proj.query"}, PROJECTOR_KEYS + FROZEN_KEYS)

    assert "projector.proj.arch_signature" in kept


def test_the_lora_phase_keeps_the_adapter_and_drops_the_frozen_base():
    keys = PROJECTOR_KEYS + FROZEN_KEYS + LORA_KEYS
    trainable = {"projector.proj.query", "projector.proj.out_proj.weight", *LORA_KEYS}

    kept = filter_with(trainable, keys)

    assert set(kept) == set(PROJECTOR_KEYS) | set(LORA_KEYS)
    assert "language_model.model.layers.0.self_attn.q_proj.weight" not in kept


def test_the_full_phase_keeps_the_language_model():
    """requires_grad is the definition, so full fine-tuning needs no special case."""
    keys = PROJECTOR_KEYS + FROZEN_KEYS
    llm_keys = {k for k in FROZEN_KEYS if k.startswith("language_model.")}
    trainable = {"projector.proj.query", "projector.proj.out_proj.weight", *llm_keys}

    kept = filter_with(trainable, keys)

    assert llm_keys <= set(kept)
    assert "vision_encoder.model.embeddings.weight" not in kept


def test_an_empty_state_dict_passes_through_untouched():
    """
    HF hands _save an empty dict on purpose when ZeRO-3 could not gather the
    16bit weights: it writes a dummy file and removes it immediately. Filtering
    that would look like the no-projector case and trigger the fallback.
    """
    method = trainer_method("_trained_state_dict")
    trainer = FakeTrainer(set(), PROJECTOR_KEYS)

    assert method(trainer, {}) == {}


def test_a_state_dict_with_no_projector_keys_falls_back_to_saving_everything(capsys):
    """
    Losing weights to save disk is far worse than saving too much. If the naming
    ever stops matching, the filter must not quietly write an empty checkpoint.
    """
    method = trainer_method("_trained_state_dict")
    trainer = FakeTrainer(set(), FROZEN_KEYS)

    kept = method(trainer, trainer.model.state_dict())

    assert set(kept) == set(FROZEN_KEYS)
    assert "경고" in capsys.readouterr().out


# ── Resume with the frozen parameters deliberately absent ────────────────────

def trainer_method_in_subclass_of(name: str, base: type) -> type:
    """
    One method of VLMTrainer, recompiled inside a synthesized subclass of `base`.

    A zero-argument super() only works when the function was compiled inside a
    class body, since that is what creates the __class__ cell it reads. Binding
    an AST-extracted function onto a type() at runtime loses that cell and
    raises "super(): __class__ cell not found", so the method has to be compiled
    as part of a real ClassDef.
    """
    tree = ast.parse(open(os.path.join(REPO_ROOT, "train.py"), encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            klass = ast.ClassDef(
                name="Extracted",
                bases=[ast.Name(id="Base", ctx=ast.Load())],
                keywords=[], body=[node], decorator_list=[], type_params=[],
            )
            module = ast.Module([klass], [])
            ast.fix_missing_locations(module)
            namespace = {"Base": base}
            exec(compile(module, "<train.py>", "exec"), namespace)
            return namespace["Extracted"]
    pytest.fail(f"VLMTrainer.{name} not found in train.py")


def warn_with(missing, unexpected, trainable, all_keys, capsys):
    calls = []

    class Base:
        FROZEN_PREFIXES = FakeTrainer.FROZEN_PREFIXES

        def _issue_warnings_after_load(self, result):
            calls.append(result)

    extracted = trainer_method_in_subclass_of("_issue_warnings_after_load", Base)

    class Result:
        missing_keys = missing
        unexpected_keys = unexpected

    trainer = extracted()
    trainer.model = FakeTrainer(trainable, all_keys).model
    trainer._issue_warnings_after_load(Result())
    return calls, capsys.readouterr().out


def test_missing_frozen_keys_are_reported_as_a_count_not_a_key_dump(capsys):
    calls, out = warn_with(
        missing=FROZEN_KEYS, unexpected=[],
        trainable={"projector.proj.query"},
        all_keys=PROJECTOR_KEYS + FROZEN_KEYS, capsys=capsys,
    )

    assert calls == [], "should not fall through to the default key dump"
    assert str(len(FROZEN_KEYS)) in out
    for key in FROZEN_KEYS:
        assert key not in out


def test_a_missing_projector_key_is_not_treated_as_frozen(capsys):
    """The guard must not cover up the one thing that would really be broken."""
    calls, _ = warn_with(
        missing=["projector.proj.query"], unexpected=[],
        trainable={"projector.proj.query"},
        all_keys=PROJECTOR_KEYS + FROZEN_KEYS, capsys=capsys,
    )

    assert len(calls) == 1, "must fall through to the default warning"


def test_a_missing_trainable_lora_key_is_not_treated_as_frozen(capsys):
    """
    A LoRA key sits under language_model., so a prefix-only check would call it
    benign. It is a weight this run trains and its absence is a real problem.
    """
    calls, _ = warn_with(
        missing=LORA_KEYS, unexpected=[],
        trainable=set(LORA_KEYS), all_keys=PROJECTOR_KEYS + LORA_KEYS, capsys=capsys,
    )

    assert len(calls) == 1


def test_unexpected_keys_always_fall_through(capsys):
    calls, _ = warn_with(
        missing=FROZEN_KEYS, unexpected=["something.stray"],
        trainable={"projector.proj.query"},
        all_keys=PROJECTOR_KEYS + FROZEN_KEYS, capsys=capsys,
    )

    assert len(calls) == 1


def test_a_clean_load_stays_on_the_default_path(capsys):
    """No missing keys is the old-checkpoint case; nothing special to say."""
    calls, out = warn_with(
        missing=[], unexpected=[],
        trainable={"projector.proj.query"},
        all_keys=PROJECTOR_KEYS + FROZEN_KEYS, capsys=capsys,
    )

    assert len(calls) == 1
    assert out == ""


def test_the_model_declares_the_attribute_hf_reaches_for():
    """
    HF's _issue_warnings_after_load reads model._keys_to_ignore_on_save whenever
    missing_keys is non-empty. Only a PreTrainedModel defines it, and the
    fall-through paths above reach that code.
    """
    from model.vlm_v2 import VisionLanguageModelV2

    assert VisionLanguageModelV2._keys_to_ignore_on_save is None


def test_save_routes_through_the_filter():
    source = trainer_source()

    assert "def _save(self" in source
    assert "_trained_state_dict" in source


# ── The regression itself ────────────────────────────────────────────────────

def test_the_config_comes_from_the_unwrapped_model():
    source = save_checkpoint_source()

    assert "getattr(self.model, 'config'" in source or 'getattr(self.model, "config"' in source


def test_the_wrapped_model_argument_is_not_used_for_the_config():
    """`model` here is the DeepSpeedEngine; its .config is a DeepSpeed dict."""
    source = save_checkpoint_source()

    assert "getattr(model, 'config'" not in source
    assert 'getattr(model, "config"' not in source


def test_a_non_vlmconfig_is_refused_rather_than_passed_to_vars():
    """An isinstance guard is what keeps vars() from seeing a dict."""
    source = save_checkpoint_source()

    assert "isinstance(config, VLMConfig)" in source


def test_vars_on_a_deepspeed_style_config_would_have_raised():
    """Pins why the guard is needed, so nobody removes it as redundant."""
    deepspeed_style_config = {"train_batch_size": 8, "bf16": {"enabled": True}}

    with pytest.raises(TypeError):
        vars(deepspeed_style_config)


# ── What the written file must contain ───────────────────────────────────────

def test_a_vlmconfig_serializes_to_the_projector_settings_a_checkpoint_needs():
    config = VLMConfig(
        projector_type="qformer",
        projector_num_query_tokens=48,
        projector_num_heads=16,
        projector_num_layers=3,
    )
    config.vision_num_patches = 576
    config.num_image_tokens = 48

    written = json.loads(
        json.dumps({k: v for k, v in vars(config).items() if not k.startswith("_")})
    )

    assert written["projector_type"] == "qformer"
    assert written["projector_num_query_tokens"] == 48
    assert written["projector_num_heads"] == 16
    assert written["projector_num_layers"] == 3


def test_the_final_save_also_writes_the_projector_settings():
    """train.py's end-of-run block uses the closure's real VLMConfig."""
    source = open(os.path.join(REPO_ROOT, "train.py"), encoding="utf-8").read()

    assert source.count("vlm_config.json") >= 2


# ── Where a checkpoint's components land ─────────────────────────────────────
# transformers' Trainer._save_checkpoint writes into
#   os.path.join(self._get_output_dir(trial), f"checkpoint-{global_step}")
# _get_output_dir alone returns the RUN directory. Using it directly put every
# checkpoint's projector at the top level, overwritten on each save, so no
# checkpoint-N directory was self-contained and no earlier checkpoint could be
# picked. Verified on the server: HF state went to checkpoint-1/ and
# checkpoint-2/ while our projector.bin went to the run directory.

def trainer_source() -> str:
    return open(os.path.join(REPO_ROOT, "train.py"), encoding="utf-8").read()


def test_the_checkpoint_dir_is_built_the_way_transformers_builds_it():
    source = trainer_source()

    assert "PREFIX_CHECKPOINT_DIR" in source
    assert "self.state.global_step" in source


def test_prefix_checkpoint_dir_is_imported_from_transformers():
    """A hand-written "checkpoint-" literal would drift from transformers."""
    from transformers.trainer_utils import PREFIX_CHECKPOINT_DIR

    assert PREFIX_CHECKPOINT_DIR == "checkpoint"
    assert "from transformers.trainer_utils import" in trainer_source()


def test_the_components_are_not_written_to_the_bare_run_directory():
    """_get_output_dir must only be used to build the checkpoint dir under it."""
    source = save_checkpoint_source()

    assert "self._get_output_dir(trial)" not in source
    assert "self._checkpoint_dir(trial)" in source


def test_super_is_called_on_every_rank_before_the_rank_zero_extras():
    """
    DeepSpeed's checkpoint write is collective, so a rank that returns early
    without calling super() deadlocks the others. super() also creates the
    directory the extras go into.
    """
    source = save_checkpoint_source()

    super_call = source.index("super()._save_checkpoint(model, trial)")
    rank_guard = source.index("if not _is_main_process():")
    assert super_call < rank_guard

    # And it must be called exactly once, not once per branch.
    assert source.count("super()._save_checkpoint(model, trial)") == 1


def test_the_projector_is_saved_for_every_train_type():
    """
    train.py sets the projector's requires_grad unconditionally, so all three
    train types train it and all three must save it.
    """
    source = save_checkpoint_source()

    save_call = "torch.save(model.projector.state_dict()"
    assert source.count(save_call) == 1, "one unconditional save, not one per branch"

    saves_at = source.index(save_call)
    for branch in ("self.train_type == 'lora'", "self.train_type == 'full'"):
        assert branch in source
        assert saves_at < source.index(branch), "the projector save must precede the branches"


# ── Auto-resume across a projector change ────────────────────────────────────
# train.py resumes from whatever get_last_checkpoint() finds in --output_dir, and
# HF Trainer restores this model with load_state_dict(state_dict, False). Now
# that projector_type is selectable, a second run with a different type pointed
# at the same output_dir hands the loader a state dict whose projector keys do
# not match, and strict=False would leave the projector randomly initialized.
# Verified on the server: transformers does abort, but inside
# _issue_warnings_after_load, on `self.model._keys_to_ignore_on_save` — an
# attribute only a PreTrainedModel has. The traceback names that attribute and
# never mentions the projector, and it arrives after the 8B LLM has loaded.

def load_resume_guard():
    """
    _require_resumable_projector, pulled out of train.py by AST.

    train.py imports transformers, peft and wandb at module scope; extracting
    the one function keeps this test independent of all three.
    """
    tree = ast.parse(open(os.path.join(REPO_ROOT, "train.py"), encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_require_resumable_projector":
            from model.checkpoint import PROJECTOR_CONFIG_KEYS, load_projector_config

            namespace = {
                "VLMConfig": VLMConfig,
                "PROJECTOR_CONFIG_KEYS": PROJECTOR_CONFIG_KEYS,
                "load_projector_config": load_projector_config,
            }
            exec(compile(ast.Module([node], []), "<train.py>", "exec"), namespace)
            return namespace["_require_resumable_projector"]
    pytest.fail("_require_resumable_projector not found in train.py")


def write_checkpoint(tmp_path, **settings) -> str:
    directory = tmp_path / "checkpoint-1"
    directory.mkdir()
    (directory / "vlm_config.json").write_text(json.dumps(settings), encoding="utf-8")
    return str(directory)


def test_resuming_with_a_different_projector_type_is_refused(tmp_path):
    guard = load_resume_guard()
    checkpoint = write_checkpoint(tmp_path, projector_type="qformer")

    with pytest.raises(SystemExit) as err:
        guard(checkpoint, VLMConfig(projector_type="mlp2x_gelu"))

    message = str(err.value)
    assert "qformer" in message and "mlp2x_gelu" in message
    assert "projector_type" in message


@pytest.mark.parametrize(
    "key, recorded, requested",
    [
        ("projector_num_query_tokens", 64, 32),
        ("projector_num_heads", 16, 8),
        ("projector_num_layers", 4, 2),
        ("projector_hidden_size", 2048, None),
    ],
)
def test_resuming_with_a_different_resampler_setting_is_refused(
    tmp_path, key, recorded, requested
):
    """Each of these changes the projector's tensors, so resume cannot restore them."""
    guard = load_resume_guard()
    checkpoint = write_checkpoint(tmp_path, projector_type="qformer", **{key: recorded})

    with pytest.raises(SystemExit) as err:
        guard(checkpoint, VLMConfig(projector_type="qformer", **{key: requested}))

    assert key in str(err.value)


def test_a_matching_checkpoint_resumes_without_complaint(tmp_path, capsys):
    """The healthy path must be silent, or the guard is useless in practice."""
    guard = load_resume_guard()
    config = VLMConfig(projector_type="qformer", projector_num_query_tokens=32)
    checkpoint = write_checkpoint(
        tmp_path,
        projector_type="qformer",
        projector_num_query_tokens=32,
        projector_num_heads=config.projector_num_heads,
        projector_num_layers=config.projector_num_layers,
        projector_ffn_ratio=config.projector_ffn_ratio,
        projector_dropout=config.projector_dropout,
        projector_hidden_size=config.projector_hidden_size,
    )

    guard(checkpoint, config)

    # load_projector_config announces which file it read, which is fine. What
    # the guard itself must not add is a warning.
    assert "경고" not in capsys.readouterr().out


def test_the_default_projector_resumes_its_own_checkpoint(tmp_path, capsys):
    """The common case: same command run twice, no projector flags at all."""
    guard = load_resume_guard()
    config = VLMConfig()
    checkpoint = write_checkpoint(
        tmp_path, **{k: getattr(config, k) for k in (
            "projector_type", "projector_num_query_tokens", "projector_num_heads",
            "projector_num_layers", "projector_ffn_ratio", "projector_dropout",
            "projector_hidden_size",
        )}
    )

    guard(checkpoint, config)

    # load_projector_config announces which file it read, which is fine. What
    # the guard itself must not add is a warning.
    assert "경고" not in capsys.readouterr().out


def test_a_checkpoint_predating_the_config_file_is_reported_not_assumed(tmp_path):
    """
    Nothing to compare against is not the same as a match. It must not raise —
    that would make every pre-existing checkpoint unresumable — but it must say
    the check did not happen.
    """
    guard = load_resume_guard()
    directory = tmp_path / "checkpoint-1"
    directory.mkdir()

    guard(str(directory), VLMConfig(projector_type="qformer"))  # must not raise


def test_a_checkpoint_predating_the_config_file_says_so(tmp_path, capsys):
    guard = load_resume_guard()
    directory = tmp_path / "checkpoint-1"
    directory.mkdir()

    guard(str(directory), VLMConfig(projector_type="qformer"))

    assert "vlm_config.json" in capsys.readouterr().out


def test_a_partially_recorded_config_compares_only_what_it_records(tmp_path):
    """
    An absent key is unknown, not a disagreement. Treating it as one would
    refuse checkpoints written by an older version of this script.
    """
    guard = load_resume_guard()
    checkpoint = write_checkpoint(tmp_path, projector_type="mlp2x_gelu")

    # mlp2x_gelu matches; the resampler keys the file omits must not be compared
    # against the dataclass defaults and reported as differences.
    guard(checkpoint, VLMConfig(projector_type="mlp2x_gelu",
                                projector_num_query_tokens=999,
                                projector_num_heads=1))


def test_the_guard_runs_before_the_model_is_built():
    """
    Placed after build_model it would still catch the mismatch, but only after
    loading an 8B LLM. The point is to fail in seconds.
    """
    source = trainer_source()

    guard_call = source.index("_require_resumable_projector(last_ckpt, config)")
    build_call = source.index("model = build_model(config, torch_dtype=dtype)")
    assert guard_call < build_call


def test_the_resume_target_is_resolved_exactly_once():
    """Two get_last_checkpoint calls could disagree if a checkpoint rotated."""
    source = trainer_source()

    assert source.count("get_last_checkpoint(args.output_dir)") == 1
