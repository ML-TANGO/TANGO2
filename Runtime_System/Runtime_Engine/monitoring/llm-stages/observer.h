// SPDX-License-Identifier: Apache-2.0
#pragma once

#include "thread_cpu.h"
#include <array>
#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <vector>
#include <cuda_runtime_api.h>

namespace tango2
{
inline int64_t nowNs()
{
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

inline int64_t blockResidualProcessingNs(int64_t finalRequestCompletion, int64_t blockEnd)
{
    if (finalRequestCompletion <= 0 || blockEnd < finalRequestCompletion)
    {
        throw std::runtime_error("invalid block residual boundaries");
    }
    return blockEnd-finalRequestCompletion;
}

inline bool mayStartBlock(bool stopped, bool budgetExceeded, bool acknowledgementFailed)
{
    return !stopped && !budgetExceeded && !acknowledgementFailed;
}

template <typename Join, typename Pop, typename Consume>
inline void drainAfterProducer(Join&& join, Pop&& pop, Consume&& consume)
{
    join();
    while (auto chunk = pop()) { consume(*chunk); }
}

inline bool tokenCountsMatch(int32_t delivered, int32_t sampled, int32_t response)
{
    return delivered == sampled && response == sampled;
}

enum class CpuBoundary { requestBegin, inputBegin, inputEnd, prefillBegin, prefillEnd, requestEnd };
inline constexpr std::array<char const*, 6> cpuBoundaryNames{
    "request_begin", "input_begin", "input_end", "prefill_begin", "prefill_end", "request_end"};

//! Shared boundaries retain raw counters; all subtraction belongs to the validator.
struct ThreadCpuObservation
{
    ThreadCpuIdentity identity;
    std::array<std::optional<ThreadCpuSnapshot>, 6> snapshots;
    std::optional<ThreadCpuSampler> sampler;

    void initialize(bool enabled)
    {
        if (enabled)
        {
            sampler.emplace();
            identity = sampler->identity();
        }
    }
    void capture(CpuBoundary boundary, int64_t at)
    {
        if (sampler) { snapshots[static_cast<size_t>(boundary)] = sampler->sample(at); }
    }
};

//! One request owns its event pool; results are read only after request completion.
struct Observation
{
    bool detail{false};
    bool baseline{false};
    bool cpuEnabled{false};
    ThreadCpuObservation workerCpu;
    int64_t inputBegin{0}, inputEnd{0}, prefillBegin{0}, prefillEnd{0};
    int64_t detokenizeNs{0}, deliverNs{0}, firstToken{0}, lastToken{0};
    int32_t inputTokens{0}, outputTokens{0}, sampledTokens{0}, eosTokens{0};
    std::vector<int32_t> eosIds;
    std::vector<int64_t> tokenTimes;
    std::array<cudaEvent_t, 258> events{};
    int32_t eventIndex{0};

    explicit Observation(bool useDetail, bool useBaseline, bool useCpu = true)
        : detail(useDetail), baseline(useBaseline), cpuEnabled(useDetail && !useBaseline && useCpu)
    {
        if (!baseline) { tokenTimes.reserve(128); }
        if (detail)
        {
            for (auto& event : events)
            {
                if (cudaEventCreate(&event) != cudaSuccess)
                {
                    for (auto created : events) { if (created) { cudaEventDestroy(created); } }
                    throw std::runtime_error("CUDA event pool allocation failed");
                }
            }
        }
    }
    Observation(Observation const&) = delete;
    Observation& operator=(Observation const&) = delete;
    ~Observation()
    {
        for (auto event : events) { if (event) { cudaEventDestroy(event); } }
    }
    void recordToken(int32_t id)
    {
        auto const time = nowNs();
        ++sampledTokens;
        for (auto eos : eosIds)
        {
            if (id == eos) { ++eosTokens; return; }
        }
        if (outputTokens == 0) { firstToken = time; }
        lastToken = time;
        ++outputTokens;
        if (!baseline) { tokenTimes.push_back(time); }
    }
    void gpuBegin(cudaStream_t stream)
    {
        if (detail && (eventIndex + 1 >= static_cast<int32_t>(events.size())
            || cudaEventRecord(events[eventIndex], stream) != cudaSuccess))
        {
            throw std::runtime_error("CUDA event start failed");
        }
    }
    void markInputBegin()
    {
        if (!baseline)
        {
            inputBegin = nowNs();
            workerCpu.capture(CpuBoundary::inputBegin, inputBegin);
        }
    }
    void markInputEnd()
    {
        if (!baseline)
        {
            inputEnd = nowNs();
            workerCpu.capture(CpuBoundary::inputEnd, inputEnd);
        }
    }
    void markPrefillBegin()
    {
        if (!baseline)
        {
            prefillBegin = nowNs();
            workerCpu.capture(CpuBoundary::prefillBegin, prefillBegin);
        }
    }
    void markPrefillEnd()
    {
        if (!baseline) { prefillEnd = nowNs(); }
    }
    void capturePrefillEndCpu()
    {
        // Preserve the first-token timestamp before reading CPU diagnostics.
        workerCpu.capture(CpuBoundary::prefillEnd, prefillEnd);
    }
    void gpuEnd(cudaStream_t stream)
    {
        if (detail)
        {
            if (cudaEventRecord(events[eventIndex+1], stream) != cudaSuccess)
            {
                throw std::runtime_error("CUDA event end failed");
            }
            eventIndex += 2;
        }
    }
    std::array<double, 2> gpuMs() const
    {
        std::array<double, 2> sums{};
        for (int32_t i = 0; i < eventIndex; i += 2)
        {
            float ms = 0;
            if (cudaEventSynchronize(events[i+1]) != cudaSuccess
                || cudaEventElapsedTime(&ms, events[i], events[i+1]) != cudaSuccess)
            {
                throw std::runtime_error("CUDA timing read failed");
            }
            sums[i == 0 ? 0 : 1] += ms;
        }
        return sums;
    }
};

inline thread_local Observation* observation = nullptr;

//! Host scopes are omitted from baseline; overlapping costs remain separate.
struct HostScope
{
    int64_t* target;
    int64_t begin;
    explicit HostScope(int64_t* destination) : target(destination), begin(destination ? nowNs() : 0) {}
    ~HostScope() { if (target) { *target += nowNs()-begin; } }
};
} // namespace tango2
