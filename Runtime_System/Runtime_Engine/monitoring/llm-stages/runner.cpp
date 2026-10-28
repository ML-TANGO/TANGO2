// SPDX-License-Identifier: Apache-2.0
#include "observer.h"
#include "run_storage.h"
#include "common/checkMacros.h"
#include "common/logger.h"
#include "common/trtUtils.h"
#include "runtime/llmInferenceRuntime.h"
#include "runtime/streaming.h"
#include <nlohmann/json.hpp>
#include <atomic>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>
#include <unistd.h>

namespace fs = std::filesystem;
using Json = nlohmann::json;
using namespace trt_edgellm;
namespace
{
volatile std::sig_atomic_t stopped = 0;
void stop(int) { stopped = 1; }
int64_t utcNs()
{
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}
void writeJson(fs::path const& file, Json const& value)
{
    fs::path temporary = file.string()+".tmp";
    std::ofstream out(temporary);
    out << value.dump() << '\n';
    out.close();
    if (!out) { throw std::runtime_error("record write failed: "+file.string()); }
    fs::rename(temporary, file);
}
void writeImmutableJson(fs::path const& file, Json const& value)
{
    if (fs::exists(file)) { throw std::runtime_error("record already exists: "+file.string()); }
    fs::path temporary = file.string()+".tmp."+std::to_string(getpid());
    std::ofstream out(temporary);
    out << value.dump() << '\n';
    out.close();
    if (!out) { throw std::runtime_error("record write failed: "+file.string()); }
    std::error_code error;
    fs::create_hard_link(temporary, file, error);
    fs::remove(temporary);
    if (error) { throw std::runtime_error("record publication failed: "+file.string()); }
}
constexpr uintmax_t kRunByteLimit = uintmax_t{1} << 30;
constexpr uintmax_t kRecordReserve = uintmax_t{1} << 20;
Json nullable(int64_t value) { return value ? Json(value) : Json(nullptr); }
Json cpuThreadJson(tango2::ThreadCpuObservation const& thread)
{
    Json snapshots = Json::object();
    for (size_t i = 0; i < thread.snapshots.size(); ++i)
    {
        if (!thread.snapshots[i]) { continue; }
        auto const& value = *thread.snapshots[i];
        snapshots[tango2::cpuBoundaryNames[i]] = {
            {"boundary_ns", value.boundaryNs}, {"read_begin_ns", value.readBeginNs},
            {"read_end_ns", value.readEndNs},
            {"on_cpu_ns", value.onCpuNs >= 0 ? Json(value.onCpuNs) : Json(nullptr)},
            {"runqueue_wait_ns", value.runqueueWaitNs >= 0 ? Json(value.runqueueWaitNs) : Json(nullptr)},
            {"runtime_error", value.runtimeError}, {"wait_error", value.waitError}};
    }
    return {{"pid", thread.identity.pid}, {"tid", thread.identity.tid},
        {"starttime_ticks", thread.identity.startTimeTicks}, {"identity_error", thread.identity.error},
        {"snapshots", snapshots}};
}
rt::LLMGenerationRequest requestFor(std::string const& prompt, int32_t limit)
{
    rt::LLMGenerationRequest request{};
    request.temperature = 1.0f;
    request.topP = 1.0f;
    request.topK = 1;
    request.maxGenerateLength = limit;
    request.saveSystemPromptKVCache = false;
    request.enableThinking = false;
    request.disableSpecDecode = true;
    rt::Message message;
    message.role = "user";
    rt::Message::MessageContent content;
    content.type = "text";
    content.content = prompt;
    message.contents.push_back(content);
    rt::LLMGenerationRequest::Request item;
    item.messages.push_back(message);
    request.requests.push_back(item);
    return request;
}

Json makeWorkload(std::string const& engine)
{
    tokenizer::Tokenizer tokenizer;
    if (!tokenizer.loadFromHF(engine)) { throw std::runtime_error("tokenizer load failed"); }
    Json cases = Json::array();
    std::array<std::string, 10> topics{"weather", "networks", "storage", "robots", "sensors",
        "software", "cameras", "energy", "timers", "memory"};
    for (int32_t target : {64, 256, 1024})
    {
        Json prompts = Json::array();
        for (auto const& topic : topics)
        {
            std::string prompt = "Write a detailed technical report about "+topic+
                ". Continue until the output limit. Background data:";
            auto count = [&]() {
                auto request = requestFor(prompt, 64);
                rt::LLMGenerationRequest::FormattedRequest formatted;
                tokenizer.applyChatTemplate(request.requests[0], formatted, true, true, false);
                return static_cast<int32_t>(tokenizer.encode(formatted.formattedCompleteRequest, false).size());
            };
            for (int32_t i = 0; count() < target && i < target; ++i) { prompt += " data"; }
            if (count() != target) { throw std::runtime_error("cannot construct exact input token fixture"); }
            prompts.push_back({{"text", prompt}, {"input_tokens", count()}});
        }
        for (int32_t output : {64, 128})
        {
            cases.push_back({{"case", "i"+std::to_string(target)+"_o"+std::to_string(output)},
                {"input_tokens", target}, {"output_limit", output}, {"prompts", prompts}});
        }
    }
    return {{"schema_version", 1}, {"cases", cases}, {"sampling", "greedy"},
        {"thinking", false}, {"prefix_reuse", false}};
}
} // namespace

int main(int argc, char** argv)
{
    int64_t const processStart = tango2::nowNs();
    try
    {
        if (argc == 4 && std::string(argv[1]) == "prepare")
        {
            writeJson(argv[3], makeWorkload(argv[2]));
            return 0;
        }
        if (argc < 7 || argc > 11)
        {
            std::cerr << "Usage: runner ENGINE WORKLOAD RUN_DIR MODE RUN_ID HEARTBEAT "
                         "[BLOCKS] [WARMUPS] [CASE,...] [CPU_MODE=on|off]\n";
            return 2;
        }
        std::string const engine = argv[1], mode = argv[4], runId = argv[5];
        fs::path const runDir = argv[3], heartbeat = argv[6];
        int32_t const blocks = argc > 7 ? std::stoi(argv[7]) : 3;
        int32_t const warmups = argc > 8 ? std::stoi(argv[8]) : 3;
        std::string const selected = argc > 9 ? argv[9] : "";
        std::string const cpuMode = argc > 10 ? argv[10] : "on";
        if ((mode != "live" && mode != "detail" && mode != "baseline") || blocks < 1 || warmups < 0
            || (cpuMode != "on" && cpuMode != "off"))
        { throw std::runtime_error("invalid mode or repetition count"); }
        fs::create_directories(runDir);
        if (fs::exists(runDir / "requests") || fs::exists(runDir / "completion.json"))
        { throw std::runtime_error("initialized run is not reusable"); }
        fs::create_directory(runDir / "requests");
        Json workload, config;
        std::ifstream(argv[2]) >> workload;
        std::ifstream(fs::path(engine)/"config.json") >> config;
        std::vector<int32_t> eos = config.at("eos_token_id").get<std::vector<int32_t>>();
        std::string bootId;
        std::ifstream("/proc/sys/kernel/random/boot_id") >> bootId;
        std::signal(SIGINT, stop);
        std::signal(SIGTERM, stop);
        gLogger.setLevel(nvinfer1::ILogger::Severity::kERROR);
        auto plugins = loadEdgellmPluginLib();
        cudaStream_t stream{};
        CUDA_CHECK(cudaStreamCreate(&stream));
        int64_t const loadBegin = tango2::nowNs();
        rt::LLMInferenceRuntime runtime(engine, "", {}, stream);
        runtime.captureDecodingCUDAGraph(stream);
        int64_t const loadEnd = tango2::nowNs();
        setProfilingEnabled(false);
        std::atomic<bool> heartbeatStop{false}, active{false}, heartbeatFailed{false};
        std::thread heart([&]() {
            while (!heartbeatStop)
            {
                try { writeJson(heartbeat, {{"pid", getpid()}, {"utc_ns", utcNs()},
                    {"monotonic_ns", tango2::nowNs()}, {"active", active.load()}, {"run_id", runId}}); }
                catch (...) { heartbeatFailed = true; }
                for (int i = 0; i < 10 && !heartbeatStop; ++i)
                { std::this_thread::sleep_for(std::chrono::milliseconds(100)); }
            }
        });
        int32_t sequence = 0, failures = 0;
        bool budgetExceeded = false, acknowledgementFailed = false;
        struct RequestResult { int64_t admission; int64_t completed; int32_t sequence; };
        auto execute = [&](Json const& fixture, int32_t promptIndex, int32_t block, bool warmup) {
            std::string const caseName = fixture.at("case");
            int32_t const input = fixture.at("input_tokens"), limit = fixture.at("output_limit");
            if (input > 2048 || input+limit > 2200 || limit > 128)
            { throw std::runtime_error("fixture exceeds engine or event-pool limits"); }
            auto request = requestFor(fixture.at("prompts").at(promptIndex).at("text"), limit);
            auto channel = rt::StreamChannel::create();
            channel->setStreamInterval(1);
            channel->setSkipSpecialTokens(true);
            request.streamChannels.push_back(channel);
            rt::LLMGenerationResponse response;
            tango2::Observation observation(mode == "detail", mode == "baseline", cpuMode == "on");
            observation.eosIds = eos;
            tango2::ThreadCpuObservation consumerCpu;
            consumerCpu.initialize(observation.cpuEnabled);
            int64_t firstText = 0, firstChunk = 0;
            int32_t delivered = 0;
            bool ok = false;
            std::atomic<bool> workerDone{false};
            std::string error;
            auto const acceptedUtc = utcNs();
            auto const a = tango2::nowNs();
            active = true;
            auto const b = tango2::nowNs();
            consumerCpu.capture(tango2::CpuBoundary::requestBegin, b);
            auto const deadline = b+int64_t{60}*1000000000;
            bool timedOut = false;
            std::thread worker([&]() {
                observation.workerCpu.initialize(observation.cpuEnabled);
                observation.workerCpu.capture(tango2::CpuBoundary::requestBegin, tango2::nowNs());
                tango2::observation = &observation;
                try { ok = runtime.handleRequest(request, response, stream); }
                catch (std::exception const& ex) { error = ex.what(); }
                tango2::observation = nullptr;
                observation.workerCpu.capture(tango2::CpuBoundary::requestEnd, tango2::nowNs());
                workerDone = true;
            });
            auto consume = [&](auto const& chunk) {
                auto const now = tango2::nowNs();
                if (!firstChunk) { firstChunk = now; }
                if (!firstText && !chunk.text.empty()) { firstText = now; }
                delivered += chunk.tokenIds.size();
                return chunk.finished;
            };
            // A bounded pop permits cancellation even when no text is produced.
            while (true)
            {
                auto chunk = channel->waitPop(std::chrono::milliseconds(100));
                if (chunk)
                {
                    if (consume(*chunk)) { break; }
                }
                if (stopped || tango2::nowNs() > deadline)
                { timedOut = !stopped; channel->cancel(); }
                if (!chunk && (channel->isFinished() || workerDone)) { break; }
            }
            tango2::drainAfterProducer([&]() { worker.join(); }, [&]() {
                return channel->waitPop(std::chrono::milliseconds(0));
            }, consume);
            auto const e = tango2::nowNs();
            consumerCpu.capture(tango2::CpuBoundary::requestEnd, e);
            active = false;
            Json gpu = Json::object();
            bool valid = ok && error.empty() && !heartbeatFailed;
            if (mode == "detail")
            {
                try { auto const times = observation.gpuMs(); gpu = {{"prefill", times[0]}, {"decode", times[1]}}; }
                catch (std::exception const& ex) { valid = false; error = ex.what(); }
            }
            std::string status = rt::finishReasonName(channel->getReason());
            if (status == "end-of-sequence") { status = "eos"; }
            if (status == "max-length") { status = "length"; }
            if (timedOut) { status = "timeout"; }
            if (!ok || !error.empty()) { status = "error"; }
            int32_t responseCount = 0;
            if (!response.outputIds.empty()) { responseCount = response.outputIds[0].size(); }
            valid = valid && observation.inputTokens == input
                && tango2::tokenCountsMatch(delivered, observation.sampledTokens, responseCount);
            if (mode == "detail") { valid = valid && observation.eventIndex/2 == observation.sampledTokens; }
            if (!valid || (status != "eos" && status != "length")) { ++failures; }
            Json stages = Json::object();
            if (mode != "baseline" && observation.prefillBegin)
            {
                stages = {{"input", observation.inputEnd-observation.inputBegin},
                    {"prefill_prepare", observation.prefillBegin-observation.inputEnd},
                    {"prefill_host", observation.prefillEnd-observation.prefillBegin},
                    {"detokenize", observation.detokenizeNs}, {"deliver", observation.deliverNs}};
                stages["host_remainder"] = e-b
                    -(observation.prefillEnd-observation.inputBegin)
                    -(observation.outputTokens >= 2 ? observation.lastToken-observation.firstToken : 0);
            }
            std::string const requestId = std::to_string(++sequence);
            Json record{{"schema_version", 1}, {"run_id", runId}, {"request_id", requestId},
                {"boot_id", bootId}, {"mode", mode}, {"case", caseName}, {"block", block},
                {"prompt_index", promptIndex}, {"warmup", warmup}, {"valid", valid}, {"status", status},
                {"a_ns", a}, {"b_ns", b}, {"e_ns", e}, {"g1_ns", nullable(observation.firstToken)},
                {"a_utc_ns", acceptedUtc},
                {"gN_ns", nullable(observation.lastToken)}, {"v1_ns", nullable(firstText)},
                {"first_chunk_ns", nullable(firstChunk)}, {"token_ns", observation.tokenTimes},
                {"input_tokens", observation.inputTokens}, {"output_tokens", observation.outputTokens},
                {"sampled_tokens", observation.sampledTokens}, {"eos_tokens", observation.eosTokens},
                {"delivered_tokens", delivered}, {"response_tokens", responseCount},
                {"stages_ns", stages}, {"gpu_ms", gpu}, {"error", error}, {"completed_utc_ns", utcNs()}};
            Json cpuThreads = Json::object();
            if (observation.cpuEnabled)
            {
                cpuThreads = {{"worker", cpuThreadJson(observation.workerCpu)},
                    {"consumer", cpuThreadJson(consumerCpu)}};
            }
            record["cpu_observation"] = {{"schema_version", 1}, {"method", "thread_clock_schedstat"},
                {"scope", "instrumented_threads"}, {"enabled", observation.cpuEnabled}, {"threads", cpuThreads}};
            if (mode == "detail") { record["gpu_event_pairs"] = observation.eventIndex/2; }
            if (record["error"].get<std::string>().size() > 4096)
            { record["error"] = record["error"].get<std::string>().substr(0, 4096); }
            writeImmutableJson(runDir/"requests"/(requestId+".json"), record);
            std::cout << runId << ' ' << caseName << ' ' << requestId << ' ' << status
                      << " tokens=" << observation.outputTokens << " valid=" << valid << '\n';
            return RequestResult{a, e, sequence};
        };
        auto reserveRecord = [&]() {
            if (tango2::runDirectoryBytes(runDir) > kRunByteLimit-kRecordReserve)
            { budgetExceeded = true; return false; }
            return true;
        };
        auto waitForAcknowledgements = [&](std::vector<int32_t> const& requests) {
            auto const deadline = tango2::nowNs()+int64_t{60}*1000000000;
            while (!stopped && tango2::nowNs() < deadline)
            {
                bool complete = true;
                for (auto request : requests)
                { complete = complete && fs::exists(runDir/"acknowledged"/(std::to_string(request)+".json")); }
                if (complete) { return true; }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            return false;
        };
        Json blockResults = Json::array();
        try
        {
            for (auto const& fixture : workload.at("cases"))
            {
                std::string const name = fixture.at("case");
                if (!selected.empty() && (","+selected+",").find(","+name+",") == std::string::npos) { continue; }
                for (int32_t i = 0; i < warmups && !stopped; ++i)
                { if (!reserveRecord()) { break; } execute(fixture, i%10, -1, true); }
            }
            for (int32_t block = 0;
                 block < blocks && tango2::mayStartBlock(stopped, budgetExceeded, acknowledgementFailed);
                 ++block)
            {
                auto const& cases = workload.at("cases");
                for (size_t index = 0; index < cases.size() && !stopped; ++index)
                {
                    auto const& fixture = cases.at((index+block)%cases.size());
                    std::string const name = fixture.at("case");
                    if (!selected.empty() && (","+selected+",").find(","+name+",") == std::string::npos) { continue; }
                    int32_t const firstRequest = sequence+1;
                    int64_t start = 0, previousEnd = 0;
                    Json gaps = Json::array();
                    std::vector<int32_t> published;
                    for (int32_t i = 0; i < 10 && !stopped; ++i)
                    {
                        if (!reserveRecord()) { break; }
                        auto result = execute(fixture, i, block, false);
                        if (!start) { start = result.admission; }
                        if (previousEnd) { gaps.push_back(result.admission-previousEnd); }
                        previousEnd = result.completed;
                        published.push_back(result.sequence);
                    }
                    bool const acknowledged = !published.empty() && waitForAcknowledgements(published);
                    auto const end = tango2::nowNs();
                    if (!acknowledged) { acknowledgementFailed = true; ++failures; }
                    blockResults.push_back({{"case", name}, {"block", block}, {"first_request", firstRequest},
                        {"last_request", sequence}, {"begin_ns", start}, {"end_ns", end},
                        {"inter_request_gaps_ns", gaps}, {"tail_processing_ns",
                            previousEnd ? tango2::blockResidualProcessingNs(previousEnd, end) : 0},
                        {"residual_acknowledged", acknowledged}});
                    if (budgetExceeded || acknowledgementFailed) { break; }
                }
            }
        }
        catch (...)
        {
            heartbeatStop = true; heart.join(); throw;
        }
        heartbeatStop = true;
        heart.join();
        writeImmutableJson(runDir/"completion.json", {{"run_id", runId}, {"mode", mode}, {"blocks", blockResults},
            {"requests", sequence}, {"failures", failures}, {"cancelled", bool(stopped)},
            {"incomplete_reason", budgetExceeded ? "run_size_limit" :
                (acknowledgementFailed ? "collector_acknowledgement_timeout" : "")},
            {"model_load_ns", loadEnd-loadBegin}, {"process_prepare_ns", loadBegin-processStart},
            {"heartbeat_failed", heartbeatFailed.load()},
            {"completed_utc_ns", utcNs()}});
        CUDA_CHECK(cudaStreamDestroy(stream));
        return failures || stopped || heartbeatFailed || budgetExceeded || acknowledgementFailed ? 1 : 0;
    }
    catch (std::exception const& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
