// SPDX-License-Identifier: Apache-2.0
#include "thread_cpu.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <exception>
#include <iostream>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>

#ifdef __linux__
#include <sched.h>
#include <time.h>
#include <unistd.h>
#endif

namespace
{
void require(bool condition, std::string const& message)
{
    if (!condition) { throw std::runtime_error(message); }
}

void parserExamples()
{
    auto const known = tango2::parseSchedstat("12345678 234567 9\n");
    require(known && known->runtimeNs == 12345678 && known->waitNs == 234567
            && known->timeslices == 9,
        "schedstat must preserve all three independent counters");
    auto const zeroWait = tango2::parseSchedstat("0 0 1\n");
    require(zeroWait && zeroWait->waitNs == 0 && zeroWait->timeslices == 1,
        "zero runnable wait is a valid measurement");
    auto const largest = tango2::parseSchedstat("18446744073709551615 0 1\n");
    require(largest && largest->runtimeNs == std::numeric_limits<uint64_t>::max(),
        "the parser must preserve representable unsigned counters");

    for (auto const* malformed : {"", "1 2", "1 2 3 4", "1 2 3 garbage",
             "-1 2 3", "1 -2 3", "1 2 -3", "1.5 2 3", "one 2 3",
             "18446744073709551616 2 3", "1 18446744073709551616 3",
             "1 2 18446744073709551616"})
    {
        require(!tango2::parseSchedstat(malformed),
            std::string("malformed schedstat must be rejected: ") + malformed);
    }
}

tango2::ThreadCpuSnapshot sample(tango2::ThreadCpuSampler& sampler)
{
    return sampler.sample(tango2::cpuMonotonicNs());
}

#ifdef __linux__
void requireCpu(tango2::ThreadCpuSnapshot const& value)
{
    require(value.onCpuNs >= 0 && value.runtimeError.empty(),
        "current-thread CPU accounting is unavailable: " + value.runtimeError);
    require(value.boundaryNs <= value.readBeginNs && value.readBeginNs <= value.readEndNs,
        "the requested boundary and counter-read interval must remain ordered");
}

bool waitAvailable(tango2::ThreadCpuSnapshot const& value, bool mandatory)
{
    if (value.runqueueWaitNs >= 0)
    {
        require(value.waitError.empty(), "available runnable wait cannot carry an error");
        return true;
    }
    require(!value.waitError.empty(), "unavailable runnable wait needs a reason");
    require(!mandatory, "runnable-wait accounting is required: " + value.waitError);
    return false;
}

int64_t clockNs(clockid_t clock)
{
    timespec value{};
    require(clock_gettime(clock, &value) == 0, "reference CPU clock read failed");
    return int64_t{value.tv_sec} * 1'000'000'000 + value.tv_nsec;
}

// CPU time bounds the work even when the test shares a busy machine. A wall
// deadline keeps an unsupported or starved environment from hanging the test.
void consumeCpu(int64_t durationNs)
{
    auto const start = clockNs(CLOCK_THREAD_CPUTIME_ID);
    auto const deadline = tango2::cpuMonotonicNs() + 2'000'000'000;
    volatile uint64_t accumulator = 1;
    while (clockNs(CLOCK_THREAD_CPUTIME_ID) - start < durationNs)
    {
        for (int i = 0; i < 4096; ++i) { accumulator = accumulator * 1664525 + 1013904223; }
        require(tango2::cpuMonotonicNs() < deadline, "CPU work exceeded its wall deadline");
    }
}

void busyAndSleep(bool requireWait)
{
    tango2::ThreadCpuSampler sampler;
    auto const& identity = sampler.identity();
    require(identity.error.empty() && identity.pid == getpid() && identity.tid > 0
            && identity.startTimeTicks > 0,
        "the sample must identify the live current thread");

    auto const beforeBusy = sample(sampler);
    consumeCpu(10'000'000);
    auto const afterBusy = sample(sampler);
    requireCpu(beforeBusy);
    requireCpu(afterBusy);
    require(afterBusy.onCpuNs - beforeBusy.onCpuNs >= 9'000'000,
        "a 10 ms CPU workload must increase current-thread runtime");

    auto const beforeSleep = sample(sampler);
    std::this_thread::sleep_for(std::chrono::milliseconds(40));
    auto const afterSleep = sample(sampler);
    requireCpu(beforeSleep);
    requireCpu(afterSleep);
    require(afterSleep.onCpuNs - beforeSleep.onCpuNs < 10'000'000,
        "blocking sleep must not be charged as CPU execution");
    bool const beforeWait = waitAvailable(beforeSleep, requireWait);
    bool const afterWait = waitAvailable(afterSleep, requireWait);
    if (beforeWait && afterWait)
    {
        auto const elapsed = afterSleep.readEndNs - beforeSleep.boundaryNs;
        auto const wait = afterSleep.runqueueWaitNs - beforeSleep.runqueueWaitNs;
        require(wait >= 0, "runnable-wait counters must not decrease");
        require(elapsed - wait >= 20'000'000,
            "the 40 ms blocking sleep must not become runnable wait");
    }
}

void helperCpuIsExcluded()
{
    tango2::ThreadCpuSampler sampler;
    auto const before = sample(sampler);
    auto const processBefore = clockNs(CLOCK_PROCESS_CPUTIME_ID);
    std::mutex mutex;
    std::condition_variable condition;
    bool go = false;
    int64_t helperRuntime = 0;
    std::exception_ptr helperError;
    std::thread helper([&]() {
        try
        {
            std::unique_lock<std::mutex> lock(mutex);
            condition.wait(lock, [&]() { return go; });
            lock.unlock();
            auto const start = clockNs(CLOCK_THREAD_CPUTIME_ID);
            consumeCpu(40'000'000);
            helperRuntime = clockNs(CLOCK_THREAD_CPUTIME_ID) - start;
        }
        catch (...) { helperError = std::current_exception(); }
    });
    {
        std::lock_guard<std::mutex> lock(mutex);
        go = true;
    }
    condition.notify_one();
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    helper.join();
    auto const processAfter = clockNs(CLOCK_PROCESS_CPUTIME_ID);
    auto const after = sample(sampler);
    if (helperError) { std::rethrow_exception(helperError); }
    requireCpu(before);
    requireCpu(after);
    require(helperRuntime >= 39'000'000 && processAfter - processBefore >= helperRuntime,
        "the helper must perform measured CPU work inside the observation window");
    require(after.onCpuNs - before.onCpuNs < helperRuntime / 2,
        "another thread's CPU work must not inflate this thread's runtime");
}

void ownershipAndWorkerLifetime(bool requireWait)
{
    tango2::ThreadCpuSampler parent;
    tango2::ThreadCpuSnapshot wrongOwner;
    tango2::ThreadCpuIdentity workerIdentity;
    tango2::ThreadCpuSnapshot workerBegin, workerEnd;
    std::exception_ptr workerError;
    std::thread worker([&]() {
        try
        {
            wrongOwner = sample(parent);
            tango2::ThreadCpuSampler own;
            workerIdentity = own.identity();
            workerBegin = sample(own);
            consumeCpu(5'000'000);
            workerEnd = sample(own);
        }
        catch (...) { workerError = std::current_exception(); }
    });
    worker.join();
    if (workerError) { std::rethrow_exception(workerError); }
    require(wrongOwner.onCpuNs < 0 && wrongOwner.runqueueWaitNs < 0
            && !wrongOwner.runtimeError.empty() && !wrongOwner.waitError.empty(),
        "reusing a sampler from another thread must reject both counters");
    require(workerIdentity.error.empty() && workerIdentity.pid == getpid()
            && workerIdentity.tid != parent.identity().tid && workerIdentity.startTimeTicks > 0,
        "the completed worker must retain its own durable identity");
    requireCpu(workerBegin);
    requireCpu(workerEnd);
    require(workerEnd.onCpuNs - workerBegin.onCpuNs >= 4'000'000,
        "worker CPU data captured before exit must survive joining the thread");
    waitAvailable(workerBegin, requireWait);
    waitAvailable(workerEnd, requireWait);
}

class AffinityGuard
{
    cpu_set_t saved{};
    bool changed{false};

public:
    AffinityGuard()
    {
        require(sched_getaffinity(0, sizeof(saved), &saved) == 0,
            "cannot inspect current allowed CPUs");
    }
    int pinToAllowedCpu()
    {
        for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu)
        {
            if (cpu == 4 || !CPU_ISSET(cpu, &saved)) { continue; }
            cpu_set_t selected;
            CPU_ZERO(&selected);
            CPU_SET(cpu, &selected);
            require(sched_setaffinity(0, sizeof(selected), &selected) == 0,
                "cannot select an already-allowed CPU for bounded contention");
            changed = true;
            return cpu;
        }
        throw std::runtime_error("no allowed contention CPU remains after excluding CPU4");
    }
    void restore()
    {
        if (!changed) { return; }
        require(sched_setaffinity(0, sizeof(saved), &saved) == 0,
            "cannot restore original CPU affinity");
        changed = false;
    }
    ~AffinityGuard()
    {
        if (changed && sched_setaffinity(0, sizeof(saved), &saved) != 0)
        { std::cerr << "ERROR: original CPU affinity restoration failed\n"; }
    }
};

void boundedContention()
{
    require(sched_getscheduler(0) == SCHED_OTHER,
        "the bounded contention example requires the ordinary fair policy");
    tango2::ThreadCpuSampler sampler;
    waitAvailable(sample(sampler), true);
    AffinityGuard affinity;
    auto const cpu = affinity.pinToAllowedCpu();
    std::atomic<bool> stop{false};
    std::mutex mutex;
    std::condition_variable condition;
    bool running = false;
    std::thread contender([&]() {
        {
            std::lock_guard<std::mutex> lock(mutex);
            running = true;
        }
        condition.notify_one();
        auto const deadline = tango2::cpuMonotonicNs() + 2'000'000'000;
        volatile uint64_t accumulator = 1;
        while (!stop.load(std::memory_order_relaxed) && tango2::cpuMonotonicNs() < deadline)
        {
            for (int i = 0; i < 4096; ++i) { accumulator = accumulator * 1664525 + 1013904223; }
        }
    });
    tango2::ThreadCpuSnapshot begin, end;
    try
    {
        std::unique_lock<std::mutex> lock(mutex);
        require(condition.wait_for(lock, std::chrono::seconds(2), [&]() { return running; }),
            "contending worker failed to start within the bound");
        lock.unlock();
        begin = sample(sampler);
        consumeCpu(60'000'000);
        end = sample(sampler);
    }
    catch (...)
    {
        stop = true;
        contender.join();
        throw;
    }
    stop = true;
    contender.join();
    affinity.restore();
    requireCpu(begin);
    requireCpu(end);
    waitAvailable(begin, true);
    waitAvailable(end, true);
    require(end.runqueueWaitNs > begin.runqueueWaitNs,
        "two runnable threads sharing one CPU must produce observed runnable wait");
    std::cout << "Contention CPU " << cpu << ": runtime_ns="
              << end.onCpuNs - begin.onCpuNs << " runqueue_wait_ns="
              << end.runqueueWaitNs - begin.runqueueWaitNs << '\n';
}
#endif
} // namespace

int main(int argc, char** argv)
{
    try
    {
        bool requireWait = false, contention = false;
        for (int i = 1; i < argc; ++i)
        {
            std::string const argument = argv[i];
            if (argument == "--require-wait") { requireWait = true; }
            else if (argument == "--contention") { contention = true; }
            else { throw std::runtime_error("unknown argument: " + argument); }
        }
        parserExamples();
#ifdef __linux__
        busyAndSleep(requireWait);
        helperCpuIsExcluded();
        ownershipAndWorkerLifetime(requireWait);
        if (contention) { boundedContention(); }
#else
        require(!requireWait && !contention, "live Linux accounting was requested on another OS");
        tango2::ThreadCpuSampler sampler;
        auto const value = sample(sampler);
        require(value.onCpuNs < 0 && value.runqueueWaitNs < 0
                && !value.runtimeError.empty() && !value.waitError.empty(),
            "unsupported platforms must report unavailable counters with reasons");
        std::cout << "Linux CPU behavior checks skipped on this platform\n";
#endif
        std::cout << "thread CPU measurement contracts passed\n";
        return 0;
    }
    catch (std::exception const& error)
    {
        std::cerr << "thread CPU measurement contract failed: " << error.what() << '\n';
        return 1;
    }
}
