"""
Check that the projector checkpoints on disk still load.

projector_type is selectable, so a projector.bin is only meaningful together with
the architecture that produced it. train.py records that architecture in a
vlm_config.json written beside the weights, and the inference entry points
rebuild from it. This walks a directory tree, finds every projector.bin, and
confirms two things for each one.

  1. It loads into a projector rebuilt purely from what its own vlm_config.json
     recorded, and the load actually moves weights.
  2. It is refused by every other architecture, which is what makes recording the
     type worth doing: without the refusal a wrong guess would load partially and
     serve a half-random projector.

Run this after any change to VisionProjector.load_weights, to the state dict
layout, or to how checkpoints are written. The unit tests cover the same ground
on small fixtures, and fixtures cannot tell you whether the artifacts you already
have on disk still load.

Usage:
    python scripts/verify_projector_checkpoints.py <directory> [more directories]

    # every checkpoint under a training output root
    python scripts/verify_projector_checkpoints.py checkpoints/

Exits non-zero when any checkpoint fails.
"""
import argparse
import contextlib
import io
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import (
    VLMConfig,
    VisionProjector,
    PROJECTOR_TYPES,
    load_projector_config,
    resolve_projector_settings,
)


def parse_args():
    p = argparse.ArgumentParser("Verify projector checkpoints on disk")
    p.add_argument("paths", nargs="+",
                   help="Directories to search recursively for projector.bin, "
                        "or projector.bin files themselves")
    p.add_argument("--vision_hidden_size", type=int, default=1024,
                   help="Vision encoder width the checkpoints were trained at "
                        "(CLIP ViT-L/14-336 = 1024, SigLIP SO400M = 1152)")
    p.add_argument("--llm_hidden_size", type=int, default=4096,
                   help="LLM width the checkpoints were trained at "
                        "(Llama 3.1-8B = 4096)")
    return p.parse_args()


def find_checkpoints(paths):
    """Every projector.bin under the given directories, in a stable order."""
    found = []
    for path in paths:
        root = os.path.abspath(os.path.expanduser(path))
        if os.path.isfile(root):
            found.append(root)
            continue
        for directory, _, filenames in os.walk(root):
            if "projector.bin" in filenames:
                found.append(os.path.join(directory, "projector.bin"))
    return sorted(set(found))


def build_projector(config: VLMConfig, projector_type: str, args) -> VisionProjector:
    return VisionProjector(
        vision_hidden_size=args.vision_hidden_size,
        llm_hidden_size=args.llm_hidden_size,
        projector_type=projector_type,
        **config.projector_kwargs(),
    )


def refusal(projector: VisionProjector, state: dict) -> str:
    """The refusal message, or an empty string when the load was accepted."""
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            projector.load_weights(state)
    except ValueError as err:
        return str(err)
    return ""


def check(weights_path: str, args) -> list:
    """Report the problems with one checkpoint. Empty list means it is fine."""
    problems = []
    recorded = load_projector_config(weights_path)
    settings, sources = resolve_projector_settings({}, recorded)
    config = VLMConfig(**settings)

    origin = sources["projector_type"]
    print(f"  projector_type = {config.projector_type}  (from {origin})")
    if origin != "checkpoint":
        # Not a failure. A checkpoint written before vlm_config.json existed
        # falls back to the dataclass default, and that default may well be
        # right. Worth saying so, because the load below then proves nothing
        # about what the checkpoint actually is.
        print("    note: no projector_type recorded beside these weights, so the "
              "default was assumed")

    state = torch.load(weights_path, map_location="cpu", weights_only=True)
    projector = build_projector(config, config.projector_type, args)
    before = {k: v.clone() for k, v in projector.state_dict().items()}

    error = refusal(projector, state)
    if error:
        problems.append(f"does not load as {config.projector_type}: "
                        f"{error.splitlines()[0]}")
        return problems

    after = projector.state_dict()
    moved = [k for k in before if k != "proj.arch_signature"
             and not torch.equal(before[k].float(), after[k].float())]
    if not moved:
        problems.append("loaded without changing a single weight")
    else:
        if config.is_resampler_projector:
            tokens = f"{config.projector_num_query_tokens} image tokens"
        else:
            tokens = "one image token per patch"
        print(f"    loaded: {len(moved)} tensors changed, {tokens}")

    accepted = [
        other for other in PROJECTOR_TYPES
        if other != config.projector_type
        and not refusal(build_projector(config, other, args), state)
    ]
    if accepted:
        problems.append(f"also accepted by {', '.join(accepted)}, so a wrong "
                        f"projector_type would load silently")
    else:
        print(f"    refused by the other {len(PROJECTOR_TYPES) - 1} architectures")

    return problems


def main():
    args = parse_args()
    checkpoints = find_checkpoints(args.paths)
    if not checkpoints:
        raise SystemExit(f"no projector.bin found under: {', '.join(args.paths)}")

    print(f"widths: vision {args.vision_hidden_size} -> LLM {args.llm_hidden_size}")
    print(f"{len(checkpoints)} checkpoint(s)\n")

    failures = {}
    for weights_path in checkpoints:
        print(weights_path)
        try:
            problems = check(weights_path, args)
        except Exception as err:  # noqa: BLE001 - one bad file must not stop the sweep
            problems = [f"{type(err).__name__}: {err}"]
        if problems:
            failures[weights_path] = problems
            for problem in problems:
                print(f"    FAIL: {problem}")
        print()

    print(f"{len(checkpoints) - len(failures)}/{len(checkpoints)} checkpoints OK")
    if failures:
        print("\nfailed:")
        for weights_path, problems in failures.items():
            print(f"  {weights_path}")
            for problem in problems:
                print(f"    {problem}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
