#!/usr/bin/env python3
"""
Auto-generate TensorBoard graph from a Llama config.json (no weight loading)
and start TensorBoard.  Invoked automatically by the Vite dev-server plugin.
"""
import json
import os
import sys
import time
import socket
import subprocess
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────
CHECKPOINT_DIR = Path('/home/etri/Downloads/Llama-3.1-8B-Instruct')
BASE_LOGDIR    = Path('/tmp/tb_logs')
MODEL_ID       = 'llama-single'
TB_PORT        = 6006
TB_BIN         = '/home/etri/miniforge3/envs/eva/bin/tensorboard'


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_port_open(port: int) -> bool:
    try:
        s = socket.create_connection(('localhost', port), timeout=0.5)
        s.close()
        return True
    except OSError:
        return False


def make_node(name, op, inputs=None):
    from tensorboard.compat.proto import node_def_pb2
    n = node_def_pb2.NodeDef()
    n.name = name
    n.op = op
    for inp in (inputs or []):
        n.input.append(inp)
    return n


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_llama_graph(config: dict):
    """
    Build a TensorBoard GraphDef from Llama config.json.
    No weights are loaded — only the computational graph topology.
    """
    from tensorboard.compat.proto import graph_pb2

    n_layers = config['num_hidden_layers']
    nodes = []

    # ── Input ──
    nodes.append(make_node('input_ids', 'Placeholder'))

    # ── Token Embedding ──
    nodes.append(make_node('model/embed_tokens/weight', 'Variable'))
    nodes.append(make_node('model/embed_tokens', 'Gather',
                            ['model/embed_tokens/weight', 'input_ids']))
    prev = 'model/embed_tokens'

    # ── Transformer Layers ──
    for i in range(n_layers):
        p = f'model/layers/{i}'

        # Pre-attention RMSNorm
        nodes.append(make_node(f'{p}/input_layernorm/weight', 'Variable'))
        nodes.append(make_node(f'{p}/input_layernorm', 'RmsNorm',
                                [prev, f'{p}/input_layernorm/weight']))

        # Grouped-Query Attention: Q / K / V projections
        for proj in ('q_proj', 'k_proj', 'v_proj'):
            nodes.append(make_node(f'{p}/self_attn/{proj}/weight', 'Variable'))
            nodes.append(make_node(f'{p}/self_attn/{proj}', 'MatMul',
                                    [f'{p}/input_layernorm',
                                     f'{p}/self_attn/{proj}/weight']))

        # RoPE positional encoding + scaled dot-product attention
        nodes.append(make_node(f'{p}/self_attn/rotary_emb', 'RoPE',
                                [f'{p}/self_attn/q_proj',
                                 f'{p}/self_attn/k_proj']))
        nodes.append(make_node(f'{p}/self_attn/sdpa', 'GroupedQueryAttn',
                                [f'{p}/self_attn/rotary_emb',
                                 f'{p}/self_attn/v_proj']))

        # Output projection
        nodes.append(make_node(f'{p}/self_attn/o_proj/weight', 'Variable'))
        nodes.append(make_node(f'{p}/self_attn/o_proj', 'MatMul',
                                [f'{p}/self_attn/sdpa',
                                 f'{p}/self_attn/o_proj/weight']))

        # Residual connection 1
        nodes.append(make_node(f'{p}/residual_1', 'Add',
                                [prev, f'{p}/self_attn/o_proj']))

        # Post-attention RMSNorm
        nodes.append(make_node(f'{p}/post_attention_layernorm/weight', 'Variable'))
        nodes.append(make_node(f'{p}/post_attention_layernorm', 'RmsNorm',
                                [f'{p}/residual_1',
                                 f'{p}/post_attention_layernorm/weight']))

        # SwiGLU MLP: gate_proj × SiLU(up_proj) → down_proj
        for proj in ('gate_proj', 'up_proj', 'down_proj'):
            nodes.append(make_node(f'{p}/mlp/{proj}/weight', 'Variable'))

        nodes.append(make_node(f'{p}/mlp/gate_proj', 'MatMul',
                                [f'{p}/post_attention_layernorm',
                                 f'{p}/mlp/gate_proj/weight']))
        nodes.append(make_node(f'{p}/mlp/up_proj', 'MatMul',
                                [f'{p}/post_attention_layernorm',
                                 f'{p}/mlp/up_proj/weight']))
        nodes.append(make_node(f'{p}/mlp/act_fn', 'SiLU',
                                [f'{p}/mlp/gate_proj']))
        nodes.append(make_node(f'{p}/mlp/gate_x_up', 'Mul',
                                [f'{p}/mlp/act_fn', f'{p}/mlp/up_proj']))
        nodes.append(make_node(f'{p}/mlp/down_proj', 'MatMul',
                                [f'{p}/mlp/gate_x_up',
                                 f'{p}/mlp/down_proj/weight']))

        # Residual connection 2
        nodes.append(make_node(f'{p}/residual_2', 'Add',
                                [f'{p}/residual_1', f'{p}/mlp/down_proj']))
        prev = f'{p}/residual_2'

    # ── Final RMSNorm ──
    nodes.append(make_node('model/norm/weight', 'Variable'))
    nodes.append(make_node('model/norm', 'RmsNorm',
                            [prev, 'model/norm/weight']))

    # ── LM Head ──
    nodes.append(make_node('lm_head/weight', 'Variable'))
    nodes.append(make_node('lm_head', 'MatMul',
                            ['model/norm', 'lm_head/weight']))
    nodes.append(make_node('logits', 'Identity', ['lm_head']))

    return graph_pb2.GraphDef(node=nodes)


def _masked_crc32(data: bytes) -> int:
    """TFRecord masked CRC32C used in TensorBoard event files."""
    import struct
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
    crc ^= 0xFFFFFFFF
    return (((crc >> 15) | (crc << 17)) + 0xA282EAD8) & 0xFFFFFFFF


def _write_tfrecord(f, data: bytes) -> None:
    """Write one TFRecord entry (length + crc_len + data + crc_data)."""
    import struct
    length = len(data)
    len_bytes = struct.pack('<Q', length)
    f.write(len_bytes)
    f.write(struct.pack('<I', _masked_crc32(len_bytes)))
    f.write(data)
    f.write(struct.pack('<I', _masked_crc32(data)))


def write_graph_event(logdir: Path, graph_def) -> None:
    from tensorboard.compat.proto.event_pb2 import Event

    logdir.mkdir(parents=True, exist_ok=True)
    fname = logdir / f'events.out.tfevents.{int(time.time())}.llama_graph'
    ev = Event()
    ev.wall_time = time.time()
    ev.step = 0
    ev.graph_def = graph_def.SerializeToString()
    with open(fname, 'wb') as f:
        _write_tfrecord(f, ev.SerializeToString())


def start_tensorboard(logdir: Path, port: int) -> None:
    subprocess.Popen(
        [TB_BIN,
         '--logdir', str(logdir),
         f'--port={port}',
         '--bind_all',
         '--reload_interval=0',
         '--load_fast=false'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Poll until TensorBoard is ready (up to 60 seconds — cold start can be slow)
    for _ in range(120):
        if is_port_open(port):
            print(f'[tb_llama] TensorBoard ready → http://localhost:{port}',
                  flush=True)
            return
        time.sleep(0.5)
    print('[tb_llama] WARNING: TensorBoard may not be ready', file=sys.stderr,
          flush=True)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    config_path = CHECKPOINT_DIR / 'config.json'

    if not config_path.exists():
        print(f'[tb_llama] ERROR: checkpoint not found at {CHECKPOINT_DIR}',
              file=sys.stderr)
        sys.exit(1)

    # Skip if already running
    if is_port_open(TB_PORT):
        print(f'[tb_llama] TensorBoard already on port {TB_PORT}', flush=True)
        return

    with open(config_path) as f:
        config = json.load(f)

    model_logdir = BASE_LOGDIR / MODEL_ID
    flag_file    = model_logdir / '.graph_ready'

    if not flag_file.exists():
        arch = config.get('architectures', ['LlamaForCausalLM'])[0]
        print(f'[tb_llama] Building {arch} graph '
              f'({config["num_hidden_layers"]} layers × '
              f'{config["num_attention_heads"]} heads)...', flush=True)
        graph = build_llama_graph(config)
        write_graph_event(model_logdir, graph)
        flag_file.touch()
        print(f'[tb_llama] Event file written → {model_logdir}', flush=True)
    else:
        print(f'[tb_llama] Reusing cached graph at {model_logdir}', flush=True)

    start_tensorboard(BASE_LOGDIR, TB_PORT)


if __name__ == '__main__':
    main()
