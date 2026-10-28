// SPDX-License-Identifier: Apache-2.0
#include "observer.h"
#include "run_storage.h"
#include <optional>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unistd.h>

void require(bool condition, char const* message)
{
    if (!condition) { throw std::runtime_error(message); }
}

int main()
{
    tango2::Observation empty(false, false);
    empty.eosIds = {10, 20};
    empty.recordToken(10);
    require(empty.sampledTokens == 1 && empty.eosTokens == 1 && empty.outputTokens == 0,
        "an EOS-only result must contain zero output tokens");
    require(empty.firstToken == 0 && empty.lastToken == 0 && empty.tokenTimes.empty(),
        "EOS cannot establish generation boundaries");

    tango2::Observation live(false, false);
    live.eosIds = {10, 20};
    live.recordToken(1);
    auto const first = live.firstToken;
    require(first > 0 && first == live.lastToken && live.tokenTimes.size() == 1,
        "one generated ID must establish one boundary pair");
    live.recordToken(20);
    require(live.outputTokens == 1 && live.lastToken == first,
        "a terminal EOS cannot extend the generated-token interval");
    live.recordToken(2);
    require(live.outputTokens == 2 && live.sampledTokens == 3 && live.tokenTimes.size() == 2,
        "token accounting must include IDs independently of text visibility");

    tango2::Observation baseline(false, true);
    baseline.recordToken(1);
    baseline.recordToken(2);
    require(baseline.outputTokens == 2 && baseline.firstToken > 0 && baseline.lastToken >= baseline.firstToken
        && baseline.tokenTimes.empty(), "baseline must retain boundaries without a token time series");

    auto const finalRawCompletion = int64_t{1'000};
    auto const publicationFinished = finalRawCompletion+250;
    require(tango2::blockResidualProcessingNs(finalRawCompletion, publicationFinished) == 250,
        "block residual time must include post-completion publication");

    bool acknowledgementFailed = false;
    int admittedBlocks = 0;
    for (int block = 0; block < 3
         && tango2::mayStartBlock(false, false, acknowledgementFailed); ++block)
    {
        ++admittedBlocks;
        acknowledgementFailed = block == 0;
    }
    require(admittedBlocks == 1,
        "a block with missing collector acknowledgements cannot admit a later block");

    struct Chunk { int32_t tokens; bool finished; };
    std::optional<Chunk> terminal;
    auto pop = [&]() -> std::optional<Chunk> {
        auto next = terminal;
        terminal.reset();
        return next;
    };
    require(!pop(), "the initial timed pop must observe an empty queue");
    int32_t delivered = 0;
    tango2::drainAfterProducer([&]() { terminal = Chunk{3, true}; }, pop,
        [&](Chunk const& chunk) { delivered += chunk.tokens; });
    require(tango2::tokenCountsMatch(delivered, 3, 3),
        "a terminal chunk queued during completion must be drained before validation");

    namespace fs = std::filesystem;
    auto const run = fs::temp_directory_path()/(
        "tango2-llm-storage-"+std::to_string(getpid())+"-"+std::to_string(tango2::nowNs()));
    fs::create_directory(run);
    try
    {
        fs::create_directories(run/"requests");
        fs::create_directories(run/"acknowledged");
        std::ofstream(run/"requests"/"1.json") << "record";
        std::ofstream(run/"acknowledged"/"1.json.tmp") << "publication in progress";
        require(tango2::runDirectoryBytes(run) == 6,
            "acknowledgement publication temporary files must not be sampled");
        fs::remove_all(run);
    }
    catch (...)
    {
        fs::remove_all(run);
        throw;
    }
    std::cout << "observer token/EOS/baseline contracts passed\n";
}
