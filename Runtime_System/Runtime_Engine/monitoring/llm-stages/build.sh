#!/usr/bin/env bash
set -euo pipefail
# Run on rtst@workstation. The input is a read-only AGX SDK snapshot, not a model.
stage_source=$(cd -- "$(dirname -- "$0")" && pwd)
stage_input=${1:?usage: build.sh /absolute/build-input}
stage_build=$(mktemp -d "${stage_input%/}/../build.XXXXXX")
stage_vendor=$stage_build/vendor
mkdir -p "$stage_vendor"
cp -a "$stage_input/home/rtst/TensorRT-Edge-LLM/." "$stage_vendor/"
python3 "$stage_source/patch_runtime.py" "$stage_vendor"
export TRT_PACKAGE_DIR=$stage_input/usr
# Match the AGX glibc/libstdc++ ABI when the workstation's cross sysroot is older.
stage_lib=$stage_input/usr/lib/aarch64-linux-gnu
stage_link_lib=$stage_build/link-libs
mkdir -p "$stage_link_lib"
ln -s "$stage_lib/libstdc++.so.6" "$stage_link_lib/libstdc++.so"
ln -s "$stage_lib/libm.so.6" "$stage_link_lib/libm.so"
printf 'GROUP ( %s %s AS_NEEDED ( %s ) )\n' \
  "$stage_lib/libc.so.6" "$stage_lib/libc_nonshared.a" \
  "$stage_input/lib/ld-linux-aarch64.so.1" > "$stage_link_lib/libc.so"
stage_cuda=$stage_input/usr/local/cuda/targets/sbsa-linux
stage_flags=(-std=c++17 -O3 -DNDEBUG -fPIC -Wall -Wextra
  -Wno-deprecated-declarations -Wno-unused-parameter
  -DTRT_EDGELLM_CUDA_LIBRARY_T_COMPAT
  -I"$stage_source" -I"$stage_vendor/cpp"
  -I"$stage_vendor/3rdParty/nlohmannJson/include"
  -I"$stage_vendor/3rdParty/stb" -I"$stage_vendor/3rdParty/miniaudio"
  -isystem "$stage_cuda/include"
  -isystem "$stage_input/usr/include/aarch64-linux-gnu")
for stage_unit in runtime/llmInferenceRuntime runtime/decoding/vanillaDecoder runtime/streaming; do
  aarch64-linux-gnu-g++ "${stage_flags[@]}" -c "$stage_vendor/cpp/$stage_unit.cpp" \
    -o "$stage_build/$(basename "$stage_unit").cpp.o"
done
cp "$stage_vendor/build/cpp/libedgellmCore.a" "$stage_build/libedgellmCore.a"
aarch64-linux-gnu-ar r "$stage_build/libedgellmCore.a" \
  "$stage_build/llmInferenceRuntime.cpp.o" "$stage_build/vanillaDecoder.cpp.o" \
  "$stage_build/streaming.cpp.o"
aarch64-linux-gnu-g++ "${stage_flags[@]}" -c "$stage_source/runner.cpp" -o "$stage_build/runner.o"
aarch64-linux-gnu-g++ "${stage_flags[@]}" "$stage_source/observer_test.cpp" \
  -L"$stage_link_lib" -L"$stage_lib" -L"$stage_cuda/lib" -lcudart \
  -Wl,-rpath,/usr/local/cuda/targets/sbsa-linux/lib -o "$stage_build/observer_test"
aarch64-linux-gnu-g++ "${stage_flags[@]}" "$stage_source/thread_cpu_test.cpp" \
  -L"$stage_link_lib" -L"$stage_lib" -pthread -o "$stage_build/thread_cpu_test"
aarch64-linux-gnu-g++ "$stage_build/runner.o" \
  "$stage_vendor/build/examples/llm/CMakeFiles/llm_stream.dir/cmake_device_link.o" \
  "$stage_build/libedgellmCore.a" \
  "$stage_vendor/build/examples/utils/libexampleUtils.a" \
  "$stage_build/libedgellmCore.a" \
  "$stage_vendor/cpp/kernels/cuteDSLArtifact/aarch64/sm_87/libcutedsl_aarch64.a" \
  -L"$stage_link_lib" -L"$stage_lib" -L"$stage_cuda/lib" -L"$stage_cuda/lib/stubs" \
  -Wl,--unresolved-symbols=ignore-in-shared-libs \
  -Wl,-rpath,/usr/local/cuda/targets/sbsa-linux/lib \
  -lnvinfer -lnvonnxparser -lcuda -lcudart -lcudadevrt -lcudart_static \
  -lrt -lpthread -ldl -o "$stage_build/runner"
sha256sum "$stage_build/runner" "$stage_build/libedgellmCore.a" \
  "$stage_build/observer_test" "$stage_build/thread_cpu_test" \
  "$stage_source/observer.h" "$stage_source/thread_cpu.h" "$stage_source/run_storage.h" \
  "$stage_source/patch_runtime.py" "$stage_source/runner.cpp" "$stage_source/build.sh" \
  > "$stage_build/BUILD.sha256"
printf '%s\n' "$stage_build"
