import argparse
import torch
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import json
from tqdm import tqdm
from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

import math
import random
prompts = json.load(open("../data/prompts.json", "r"))
basic_prompt = prompts["optimizer"]
silver_prompt = prompts["s_r"]
golden_prompt = prompts["g_r"]
judge_prompt = prompts["discriminator"]

def run_eval(model_path, max_target_len, question_file, answer_file, temperature, top_p, gpus, load_in_8bit):
    """
    Step 1: generate optimized prompt based on raw prompt, optional raw response and optional golden response (Case 0/1/2/3/4/5)
    Step 2: depend whether optimized prompt is better than raw prompt (Case 0/1/2/3/4/5), if not, treat raw prompt as "new" prompt
    Step 3: generate optional optimized|new response (Case 1/4|6 - multichoice & Case 2/5|7 - generation)
    Step 4: pack optimized prompt, optional optimized response and optional golden response as new inputs for next epoch, update labels (Case 0/1/2/3/4/5/6/7)

    Case 0: raw prompt -> chatgpt prompt & gpt4 prompt => optimized prompt -> raw prompt & gpt4 prompt
    Case 1: [multichoice] raw prompt + raw response -> A or B => [multichoice] optimized prompt + optimized response -> A or B
    Case 2: [generation] raw prompt + raw response -> chatgpt prompt & gpt4 prompt => [generation] optimized prompt + optimized response -> raw prompt & gpt4 prompt
    Case 3: raw prompt + golden response -> chatgpt prompt & gpt4 prompt => optimized prompt + golden response -> raw prompt & gpt4 prompt
    Case 4: [multichoice] raw prompt + raw response + golden response -> A or B 
            => [multichoice] optimized prompt + optimized response + golden response -> A or B
    Case 5: [generation] raw prompt + raw response + golden response -> chatgpt prompt & gpt4 prompt
            => [generation] optimized prompt + optimized response + golden response -> raw prompt & gpt4 prompt
    Case 6: [multichoice] raw prompt -> A or B => [multichoice] raw prompt -> A or B
    Case 7: [generation] raw prompt -> davinci response & gpt4 response => [generation] raw prompt -> new response & gpt4 response
    Case 8: chatgpt prompt + gpt4 prompt -> A or B => chatgpt prompt + gpt4 prompt -> A or B
    """
    os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(gpus)
    p_sampling_params = SamplingParams(max_tokens=256, temperature=temperature, top_p=top_p)
    r_sampling_params = SamplingParams(max_tokens=512, temperature=temperature, top_p=top_p)
    ques_file = open(os.path.expanduser(question_file), "r").readlines()

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    d_sampling_params = SamplingParams(max_tokens=1, temperature=temperature, top_p=top_p)

    qs_p = []  # case in step 1
    qs_p_ids = {}  # original line no to qs_p_id
    qs_r_g = []  # case in step 3
    qs_r_g_ids = {}  # original line no to [generation] qs_r_g_id
    qs_r_m = []  # case in step 3
    qs_r_m_ids = {}  # original line no to [multichoice] qs_r_m_id
    qs_d = []  # case in step 2
    d_acc_inputs = []  # use for packing
    s_ps = []  # use for packing
    r_ps = []  # use for packing
    p_os = []  # use for packing
    qs_p2r_g_ids = {}  # qs_p_id to qs_r_g_id in Case 1 and 4
    qs_p2r_m_ids = {}  # qs_p_id to qs_r_m_id in Case 2 and 5
    for l_i, line in enumerate(ques_file):
        d_line = json.loads(line)
        qs_input = d_line["prompt"]

        # collect data for optimized prompt generation
        if d_line["case_type"] in [0, 1, 2, 3, 4, 5]:
            t_qs_input = tokenizer.encode(qs_input)
            if len(t_qs_input) > 4096:
                w_qs_input = qs_input.split(" ")
                qs_p.append(" ".join(w_qs_input[-int(4000 * len(w_qs_input) / len(t_qs_input)):]))
            else:
                qs_p.append(qs_input)
            qs_p_ids[l_i] = len(qs_p) - 1
            qs_d.append(d_line["g_r"])
            d_acc_inputs.append([d_line["g_r"], d_line["rejected"]])
            s_ps.append(d_line["s_p"])
            r_ps.append(d_line["r_p"])
            p_os.append(d_line["p_o"])
        
        # collect data for optimized response generation
        if d_line["case_type"] in [1, 4, 6]:
            qs_r_m.append(qs_input)
            qs_r_m_ids[l_i] = len(qs_r_m) - 1
            if d_line["case_type"] in [1, 4]:
                qs_p2r_m_ids[qs_p_ids[l_i]] = len(qs_r_m) - 1
        elif d_line["case_type"] in [2, 5, 7]:
            qs_r_g.append(qs_input)
            qs_r_g_ids[l_i] = len(qs_r_g) - 1
            if d_line["case_type"] in [2, 5]:
                qs_p2r_g_ids[qs_p_ids[l_i]] = len(qs_r_g) - 1

    model_path = os.path.expanduser(model_path)
    model = LLM(model=model_path, gpu_memory_utilization=0.85, tensor_parallel_size=len(gpus), max_num_batched_tokens=4096)

    # step 1: gen optimized prompt based on raw prompt
    p_outputs = model.generate(qs_p, p_sampling_params)

    # step 2: judge whether optimized prompt or raw prompt is better
    d_acc_inputs_s = []
    for p_i, p_output in enumerate(p_outputs):
        p_outputs[p_i] = p_output.outputs[0].text.strip() + p_os[p_i]

        # eliminate possible redundant prefix
        p_outputs[p_i] = p_outputs[p_i].replace("Golden Prompt:", "").strip()

        qs_d_v = qs_d[p_i]
        qs_d[p_i] = judge_prompt.replace("R_P", r_ps[p_i]).replace("P_A", p_outputs[p_i]).replace("P_B", s_ps[p_i]).replace("G_R", qs_d_v)
        d_acc_inputs_v = d_acc_inputs[p_i]
        d_acc_inputs_s.append(judge_prompt.replace("R_P", r_ps[p_i]).replace("P_A", d_acc_inputs_v[1]).replace("P_B", s_ps[p_i]).replace("G_R", d_acc_inputs_v[0]))
    d_outputs = model.generate(qs_d, d_sampling_params)

    # use training samples to calculate the discriminator accuracy
    d_acc_outputs = model.generate(d_acc_inputs_s, d_sampling_params)
    d_acc_count = 0
    d_acc_num = 0
    for d_acc_i, d_acc_output in enumerate(d_acc_outputs):
        option_output = d_acc_output.outputs[0].text.strip().lower()
        if option_output in ["a", "b"]:
            if option_output == "a":
                d_acc_count += 1
            d_acc_num += 1
    if d_acc_num != 0:
        print("Discriminator accuracy: {}%, testing on {} training cases".format(round(d_acc_count / d_acc_num * 100, 2), d_acc_num))

    d_acc_count_t = 0
    for d_i, d_output in enumerate(d_outputs):
        option_output = d_output.outputs[0].text.strip().lower()
        if option_output == "a":
            d_acc_count_t += 1
        else:
            p_outputs[d_i] = s_ps[d_i]
    print("Discriminator selection: {}%".format(round(d_acc_count_t / len(d_outputs) * 100, 2)))

    # step 3: gen optional optimized response
    for p_i, p_output in enumerate(p_outputs):
        if p_i in qs_p2r_g_ids:
            qs_r_g[qs_p2r_g_ids[p_i]] = p_output
        if p_i in qs_p2r_m_ids:
            qs_r_m[qs_p2r_m_ids[p_i]] = p_output
    r_g_outputs = model.generate(qs_r_g, r_sampling_params)
    r_m_outputs = []
    for r_m_output in model.generate(qs_r_m, d_sampling_params):
        option_output = r_m_output.outputs[0].text.strip().lower()
        if option_output not in ["a", "b"]:
            option_output = random.choice(["A", "B"])
        r_m_outputs.append(option_output)

    # step 4: pack new task prompt
    with open(os.path.expanduser(answer_file), "w") as ans_file:
        for l_i, line in enumerate(ques_file):
            d_line = json.loads(line)

            if d_line["case_type"] == 0:
                new_prompt = basic_prompt.replace("O_C", "")
                new_s_p = p_outputs[qs_p_ids[l_i]]
                new_s_r = ""
            elif d_line["case_type"] == 1:
                new_prompt = basic_prompt.replace("O_C", silver_prompt)
                new_s_p = p_outputs[qs_p_ids[l_i]]
                new_s_r = r_m_outputs[qs_r_m_ids[l_i]]
            elif d_line["case_type"] == 2:
                new_prompt = basic_prompt.replace("O_C", silver_prompt)
                new_s_p = p_outputs[qs_p_ids[l_i]]
                new_s_r = r_g_outputs[qs_r_g_ids[l_i]].outputs[0].text.strip()
            elif d_line["case_type"] == 3:
                new_prompt = basic_prompt.replace("O_C", golden_prompt)
                new_s_p = p_outputs[qs_p_ids[l_i]]
                new_s_r = ""
            elif d_line["case_type"] == 4:
                new_prompt = basic_prompt.replace("O_C", silver_prompt + golden_prompt)
                new_s_p = p_outputs[qs_p_ids[l_i]]
                new_s_r = r_m_outputs[qs_r_m_ids[l_i]]
            elif d_line["case_type"] == 5:
                new_prompt = basic_prompt.replace("O_C", silver_prompt + golden_prompt)
                new_s_p = p_outputs[qs_p_ids[l_i]]
                new_s_r = r_g_outputs[qs_r_g_ids[l_i]].outputs[0].text.strip()
            elif d_line["case_type"] == 6:
                new_prompt = d_line["prompt"]
                new_s_p = d_line["prompt"]
                new_s_r = r_m_outputs[qs_r_m_ids[l_i]]
                d_line["rejected"] = new_s_r
            elif d_line["case_type"] == 7:
                new_prompt = d_line["prompt"]
                new_s_p = d_line["prompt"]
                new_s_r = r_g_outputs[qs_r_g_ids[l_i]].outputs[0].text.strip()
                d_line["rejected"] = new_s_r
            else:
                if random.uniform(0, 1) <= 0.5:
                    # gradually reduce the scale of discriminator data, since this is an easier task
                    new_prompt = d_line["prompt"]
                    new_s_p = d_line["s_p"]
                    new_s_r = ""
                else:
                    continue
            
            new_prompt = new_prompt.replace("S_P", new_s_p).replace("S_R", new_s_r).replace("G_R", d_line["g_r"]).replace("G_N", str(len(d_line["chosen"].split(" "))))
            if d_line["case_type"] not in [6, 7, 8]:
                new_prompt = "<|user|>\n" + new_prompt + "<|assistant|>\n"
            
            ans_file.write(json.dumps({
                "id": d_line["id"], 
                "prompt": new_prompt, 
                "chosen": d_line["chosen"], 
                "rejected": d_line["rejected"],
                "s_p": new_s_p,
                "r_p": d_line["r_p"],
                "g_r": d_line["g_r"],
                "p_o": d_line["p_o"],
                "case_type": d_line["case_type"]
                }) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, required=True)
    parser.add_argument("--question-file", type=str, required=True)
    parser.add_argument("--answer-file", type=str, default="answer.jsonl")
    parser.add_argument("--max-target-len", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--num-gpus", type=int, default=1)
    parser.add_argument("--num-partitions", type=int, default=1, choices=[1, 2, 4, 8])
    parser.add_argument("--load-in-8bit", action="store_true")
    args = parser.parse_args()

    if args.num_partitions > 1:
        assert args.num_gpus % args.num_partitions == 0
        # try parition data & resources in advance
        org_questions = open(os.path.expanduser(args.question_file), "r").readlines()
        tmp_question_files = []
        tmp_answer_files = []
        for i in range(args.num_partitions):
            tmp_question_file_path = "{}-{}.{}".format(".".join(args.question_file.split(".")[:-1]), i, args.question_file.split(".")[-1])
            tmp_answer_file_path = "{}-{}.{}".format(".".join(args.question_file.split(".")[:-1]), i, args.answer_file.split(".")[-1])
            w = open(tmp_question_file_path, "w")
            start = i * (len(org_questions) // args.num_partitions)
            end = (i + 1) * (len(org_questions) // args.num_partitions)

            if i == args.num_partitions - 1:
                end = max(end, len(org_questions))

            for org_question in org_questions[start:end]:
                w.write(org_question)
            w.close()
            tmp_question_files.append(tmp_question_file_path)
            tmp_answer_files.append(tmp_answer_file_path)
        # run eval parallel
        from multiprocessing import Pool
        with Pool(args.num_partitions) as p:
            p.starmap(
                run_eval, 
                [
                    (
                        args.model_path, 
                        args.max_target_len,
                        tmp_question_files[i],
                        tmp_answer_files[i],
                        args.temperature,
                        args.top_p,
                        [str(u) for u in range(args.num_gpus // args.num_partitions * i, args.num_gpus // args.num_partitions * (i + 1))],
                        args.load_in_8bit
                    ) for i in range(args.num_partitions)
                ]
            )
        # merge answer files
        wa = open(args.answer_file, "w")
        for tmp_answer_file in tmp_answer_files:
            for line in open(tmp_answer_file, "r").readlines():
                wa.write(line)
        wa.close()
        # clean tmp files
        for i, tmp_answer_file in enumerate(tmp_answer_files):
            os.system("rm -f {}".format(tmp_question_files[i]))
            os.system("rm -f {}".format(tmp_answer_file))
    else:
        run_eval(
            args.model_path,
            args.max_target_len,
            args.question_file,
            args.answer_file,
            args.temperature,
            args.top_p,
            [str(u) for u in range(args.num_gpus)],
            args.load_in_8bit
        )
