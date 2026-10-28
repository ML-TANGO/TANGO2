"""Apply exact, version-pinned hooks to a disposable runtime source snapshot."""

import argparse
import pathlib


def replace(source, old, new, count=1):
    if source.count(old) != count:
        raise RuntimeError(f"runtime source changed: expected {count} matches: {old[:90]}")
    return source.replace(old, new)


def patch(root):
    runtime = root / "cpp/runtime/llmInferenceRuntime.cpp"
    text = runtime.read_text()
    text = replace(text, '#include "runtime/decoding/decoderRegistry.h"',
                   '#include "runtime/decoding/decoderRegistry.h"\n#include "observer.h"')
    text = replace(text, "    // Apply chat template for all requests",
                   "    if (tango2::observation) { tango2::observation->markInputBegin(); }\n"
                   "    // Apply chat template for all requests")
    text = replace(text, "    // Forward sampling params to context;", """    if (tango2::observation)
    {
        tango2::observation->markInputEnd();
        tango2::observation->inputTokens = context.rawBatchedInputIds.at(0).size();
    }
    // Forward sampling params to context;""")
    text = replace(text, "    bool const prefillStatus = runBaseModelPrefill(context);", """    if (tango2::observation) { tango2::observation->markPrefillBegin(); }
    bool const prefillStatus = runBaseModelPrefill(context);
    if (tango2::observation)
    {
        tango2::observation->markPrefillEnd();
        if (prefillStatus) { tango2::observation->recordToken(context.tokenIds.at(0).back()); }
        tango2::observation->capturePrefillEndCpu();
    }""")
    text = replace(text, "        // Per-iter pipeline: decode → finalize finish state → emit chunks.",
                   "        if (tango2::observation) { tango2::observation->recordToken(context.tokenIds.at(0).back()); }\n"
                   "        // Per-iter pipeline: decode → finalize finish state → emit chunks.")
    text = replace(text, "    TIME_STAGE(metrics::StageNames::kLLM_PREFILL, context.stream);",
                   "    if (tango2::observation) { tango2::observation->gpuBegin(context.stream); }\n"
                   "    TIME_STAGE(metrics::StageNames::kLLM_PREFILL, context.stream);")
    # This exact D2H+sync boundary belongs only to base prefill in this source.
    old = "        activeBatchSize * sizeof(int32_t), cudaMemcpyDeviceToHost, context.stream));\n    CUDA_CHECK(cudaStreamSynchronize(context.stream));"
    text = replace(text, old, old.replace("    CUDA_CHECK", "    if (tango2::observation) { tango2::observation->gpuEnd(context.stream); }\n    CUDA_CHECK"))
    runtime.write_text(text)

    decoder = root / "cpp/runtime/decoding/vanillaDecoder.cpp"
    text = decoder.read_text()
    text = replace(text, '#include "sampler/sampling.h"', '#include "sampler/sampling.h"\n#include "observer.h"')
    text = replace(text, "    TIME_STAGE(metrics::StageNames::kLLM_GENERATION, context.stream);",
                   "    if (tango2::observation) { tango2::observation->gpuBegin(context.stream); }\n"
                   "    TIME_STAGE(metrics::StageNames::kLLM_GENERATION, context.stream);")
    text = replace(text, "    CUDA_CHECK(cudaStreamSynchronize(context.stream));",
                   "    if (tango2::observation) { tango2::observation->gpuEnd(context.stream); }\n"
                   "    CUDA_CHECK(cudaStreamSynchronize(context.stream));")
    decoder.write_text(text)

    streaming = root / "cpp/runtime/streaming.cpp"
    text = streaming.read_text()
    text = replace(text, '#include "tokenizer/tokenizer.h"', '#include "tokenizer/tokenizer.h"\n#include "observer.h"')
    for function, member in (("decodePerSlot(DecodingInferenceContext& context, tokenizer::Tokenizer const& tok)", "detokenizeNs"),
                             ("emitChunks(DecodingInferenceContext& context)", "deliverNs")):
        text = replace(text, "void " + function + "\n{", "void " + function + "\n{\n"
                       "    tango2::HostScope timing(tango2::observation && !tango2::observation->baseline\n"
                       f"        ? &tango2::observation->{member} : nullptr);")
    streaming.write_text(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=pathlib.Path)
    patch(parser.parse_args().snapshot)
