import argparse
import torch
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import json
from tqdm import tqdm
from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

def run_eval(model_path, max_target_len, question_file, answer_file, temperature, top_p, gpus, load_in_8bit):
    os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(gpus)
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    qs = []
    qs_ids = []
    qs_icls = []
    qs_ends = []
    with open(os.path.expanduser(question_file), "r") as ques_file:
        for line in ques_file:
            d_line = json.loads(line)
            qs_input = d_line["text"]
            if "prefix" in d_line:
                qs_input = d_line["prefix"] + qs_input + d_line["postfix"]
            t_qs_input = tokenizer.encode(qs_input)
            if len(t_qs_input) > 4096:
                w_qs_input = qs_input.split(" ")
                qs.append(" ".join(w_qs_input[-int(4000 * len(w_qs_input) / len(t_qs_input)):]))
            else:
                qs.append(qs_input)
            qs_ids.append(d_line["question_id"])
            if "icl" in d_line:
                qs_icls.append(d_line["icl"])
                qs_ends.append(d_line["end"])

    model_path = os.path.expanduser(model_path)
    model = LLM(model=model_path, gpu_memory_utilization=0.85, tensor_parallel_size=len(gpus), max_model_len=4096, max_num_batched_tokens=4096, trust_remote_code=True)
    sampling_params = SamplingParams(max_tokens=max_target_len, temperature=temperature, top_p=top_p)

    outputs = [output.outputs[0].text.strip() for output in model.generate(qs, sampling_params)]

    print(outputs[:10])
    
    with open(os.path.expanduser(answer_file), "w") as ans_file:
        for i_d, output in enumerate(outputs):
            output = output.replace("Golden Prompt:", "").strip()
            if len(qs_icls) > 0:
                ans_file.write(json.dumps({"question_id": qs_ids[i_d], "text": output, "prefix": qs_icls[i_d], "postfix": qs_ends[i_d]}) + "\n")
            else:
                ans_file.write(json.dumps({"question_id": qs_ids[i_d], "text": output}) + "\n")

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
