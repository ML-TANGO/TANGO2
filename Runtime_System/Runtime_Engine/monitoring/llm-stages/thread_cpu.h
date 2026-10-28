// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <array>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <limits>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>

#if defined(__linux__)
#include <cerrno>
#include <fcntl.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#endif

namespace tango2
{
inline int64_t cpuMonotonicNs()
{
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

struct SchedstatValues
{
    uint64_t runtimeNs{0}, waitNs{0}, timeslices{0};
};

inline std::optional<uint64_t> parseCpuUnsigned(std::string_view token)
{
    uint64_t value{};
    if (token.empty()) { return std::nullopt; }
    auto const parsed = std::from_chars(token.data(), token.data()+token.size(), value);
    if (parsed.ec != std::errc{} || parsed.ptr != token.data()+token.size()) { return std::nullopt; }
    return value;
}

//! /proc/<tid>/schedstat is exactly three unsigned decimal counters.
inline std::optional<SchedstatValues> parseSchedstat(std::string const& text)
{
    std::istringstream input(text);
    std::array<uint64_t, 3> values{};
    std::string token;
    for (auto& value : values)
    {
        if (!(input >> token)) { return std::nullopt; }
        auto const parsed = parseCpuUnsigned(token);
        if (!parsed) { return std::nullopt; }
        value = *parsed;
    }
    if (input >> token) { return std::nullopt; }
    return SchedstatValues{values[0], values[1], values[2]};
}

struct ThreadCpuIdentity
{
    int64_t pid{0}, tid{0};
    uint64_t startTimeTicks{0};
    std::string error;
};

struct ThreadCpuSnapshot
{
    int64_t boundaryNs{0}, readBeginNs{0}, readEndNs{0};
    int64_t onCpuNs{-1}, runqueueWaitNs{-1};
    std::string runtimeError, waitError;
};

//! A sampler belongs to one live thread. No reads are deferred until after join().
class ThreadCpuSampler
{
public:
    ThreadCpuSampler()
    {
#if defined(__linux__)
        mIdentity.pid = getpid();
        mIdentity.tid = syscall(SYS_gettid);
        std::ifstream input("/proc/thread-self/stat");
        std::string stat;
        std::getline(input, stat);
        auto const open = stat.find('('), close = stat.rfind(')');
        auto const separator = stat.find(' ');
        if (open == std::string::npos || close == std::string::npos || close <= open
            || separator == std::string::npos)
        {
            mIdentity.error = "thread_stat_unavailable";
        }
        else
        {
            auto const tid = parseCpuUnsigned(std::string_view(stat).substr(0, separator));
            std::istringstream fields(stat.substr(close+1));
            std::string token;
            // The parenthesized comm is field 2; starttime is field 22.
            for (int field = 3; field <= 22 && fields; ++field) { fields >> token; }
            std::optional<uint64_t> start;
            if (fields) { start = parseCpuUnsigned(token); }
            if (!tid || *tid != static_cast<uint64_t>(mIdentity.tid) || !start || *start == 0)
            {
                mIdentity.error = "thread_identity_invalid";
            }
            else { mIdentity.startTimeTicks = *start; }
        }
        mSchedstat = ::open("/proc/thread-self/schedstat", O_RDONLY | O_CLOEXEC);
        if (mSchedstat < 0) { mWaitError = "schedstat_unavailable"; }
#else
        mIdentity.error = "unsupported_platform";
        mWaitError = "unsupported_platform";
#endif
    }

    ~ThreadCpuSampler()
    {
#if defined(__linux__)
        if (mSchedstat >= 0) { ::close(mSchedstat); }
#endif
    }
    ThreadCpuSampler(ThreadCpuSampler const&) = delete;
    ThreadCpuSampler& operator=(ThreadCpuSampler const&) = delete;

    ThreadCpuIdentity const& identity() const { return mIdentity; }

    ThreadCpuSnapshot sample(int64_t boundaryNs)
    {
        ThreadCpuSnapshot result;
        result.boundaryNs = boundaryNs;
        result.readBeginNs = cpuMonotonicNs();
#if defined(__linux__)
        if (getpid() != mIdentity.pid || syscall(SYS_gettid) != mIdentity.tid)
        {
            result.runtimeError = result.waitError = "thread_identity_mismatch";
        }
        else if (!mIdentity.error.empty())
        {
            result.runtimeError = result.waitError = mIdentity.error;
        }
        else
        {
            timespec cpu{};
            if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu) != 0 || cpu.tv_sec < 0
                || cpu.tv_nsec < 0 || cpu.tv_nsec >= 1'000'000'000
                || cpu.tv_sec > (std::numeric_limits<int64_t>::max()-cpu.tv_nsec)/1'000'000'000)
            {
                result.runtimeError = "thread_clock_unavailable";
            }
            else { result.onCpuNs = int64_t{cpu.tv_sec}*1'000'000'000+cpu.tv_nsec; }

            if (mSchedstat < 0) { result.waitError = mWaitError; }
            else
            {
                std::array<char, 256> buffer{};
                ssize_t size;
                do { size = pread(mSchedstat, buffer.data(), buffer.size(), 0); }
                while (size < 0 && errno == EINTR);
                if (size <= 0 || static_cast<size_t>(size) == buffer.size())
                {
                    result.waitError = "schedstat_read_failed";
                }
                else
                {
                    auto const counters = parseSchedstat(std::string(buffer.data(), static_cast<size_t>(size)));
                    if (!counters || counters->waitNs > static_cast<uint64_t>(std::numeric_limits<int64_t>::max()))
                    {
                        result.waitError = "schedstat_invalid";
                    }
                    else if (!counters->timeslices) { result.waitError = "schedstat_inactive"; }
                    else { result.runqueueWaitNs = static_cast<int64_t>(counters->waitNs); }
                }
            }
        }
#else
        result.runtimeError = result.waitError = "unsupported_platform";
#endif
        result.readEndNs = cpuMonotonicNs();
        return result;
    }

private:
    ThreadCpuIdentity mIdentity;
#if defined(__linux__)
    int mSchedstat{-1};
#endif
    std::string mWaitError;
};
} // namespace tango2
