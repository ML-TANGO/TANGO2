import json
import random

random.seed(2024)

prompts = json.load(open("../data/prompts.json", "r"))
basic_prompt = prompts["optimizer"]
silver_prompt = prompts["s_r"]
golden_prompt = prompts["g_r"]
judge_prompt = prompts["discriminator"]

data = open("../data/final_collected_data.jsonl", "r").readlines()
new_data = []
w_dpo = open("../data/dpo_train_data_3W.jsonl", "w")
w_ipl = open("../data/ipl_train_data_3W.jsonl", "w")
for d in data:
    d = json.loads(d)
    c_id = d["id"]
    raw_prompt = d["raw_prompt"]
    raw_raw_prompt = raw_prompt
    gpt4_response = d["gpt4_response_based_raw"]
    raw_gpt4_response = gpt4_response
    text003_response = d["text003_response_based_raw"]
    chatgpt_prompt = d["chatgpt_optimized_prompt"]
    gpt4_prompt = d["gpt4_optimized_prompt"]
    post_options = ""

    # modify generation format as multichoice
    if random.uniform(0, 1) <= 0.5:
        if random.uniform(0, 1) <= 0.5:
            raw_prompt = raw_prompt + "\n" + "A: " + text003_response + "\n" + "B: " + gpt4_response + "\nAnswer:"
            post_options = "\n" + "A: " + text003_response + "\n" + "B: " + gpt4_response + "\nAnswer:"
            gpt4_response = "B"
            text003_response = "A"
            if random.uniform(0, 1) <= 0.2:
                text003_response = "B"
        else:
            raw_prompt = raw_prompt + "\n" + "A: " + gpt4_response + "\n" + "B: " + text003_response + "\nAnswer:"
            post_options = "\n" + "A: " + gpt4_response + "\n" + "B: " + text003_response + "\nAnswer:"
            gpt4_response = "A"
            text003_response = "B"
            if random.uniform(0, 1) <= 0.2:
                text003_response = "A"

    # prompt optimization data
    random_num = random.choice([0, 1, 2, 3])
    if random_num == 0:
        new_prompt = basic_prompt.replace("O_C", "")
        case_type = 0
    elif random_num == 1:
        new_prompt = basic_prompt.replace("O_C", silver_prompt)
        if gpt4_response in ["A", "B"]:
            case_type = 1
        else:
            case_type = 2
    elif random_num == 2:
        new_prompt = basic_prompt.replace("O_C", golden_prompt)
        case_type = 3
    elif random_num == 3:
        new_prompt = basic_prompt.replace("O_C", silver_prompt + golden_prompt)
        if gpt4_response in ["A", "B"]:
            case_type = 4
        else:
            case_type = 5
    
    new_prompt = new_prompt.replace("S_P", raw_prompt).replace("S_R", text003_response).replace("G_R", gpt4_response).replace("G_N", str(len(gpt4_prompt.split(" "))))
    new_prompt = "<|user|>\n" + new_prompt + "<|assistant|>\n"

    # sft data
    new_data.append({
        "id": c_id, 
        "conversations": [
            {"role": "user", "value": new_prompt},
            {"role": "bot", "value": gpt4_prompt}
        ]
    })

    # dpo data
    w_dpo.write(json.dumps({
        "id": c_id, 
        "prompt": new_prompt,
        "rejected": chatgpt_prompt,
        "chosen": gpt4_prompt
    }) + "\n")

    # ipl data
    w_ipl.write(json.dumps({
        "id": c_id, 
        "prompt": new_prompt,
        "rejected": chatgpt_prompt,
        "chosen": gpt4_prompt,
        "s_p": raw_prompt,
        "r_p": raw_raw_prompt,
        "g_r": gpt4_response,
        "p_o": post_options,
        "case_type": case_type
    }) + "\n")

    # additional discriminator and instruciton data for ipl
    random_num = random.choice([4, 5])
    if random_num == 4:
        new_prompt = "Answer the question with no more than G_N words: {}".format(raw_prompt)
        gpt4_prompt = gpt4_response
        chatgpt_prompt = text003_response
        if gpt4_response in ["A", "B"]:
            case_type = 6
        else:
            case_type = 7
        B_prompt, A_prompt = "", ""
    elif random_num == 5:
        new_prompt = judge_prompt
        if random.uniform(0, 1) <= 0.5:
            B_prompt = gpt4_prompt
            A_prompt = chatgpt_prompt
            gpt4_prompt = "B"
            chatgpt_prompt = "A"
        else:
            B_prompt = chatgpt_prompt
            A_prompt = gpt4_prompt
            gpt4_prompt = "A"
            chatgpt_prompt = "B"
        case_type = 8
    
    new_prompt = new_prompt.replace("R_P", raw_prompt).replace("P_A", A_prompt).replace("P_B", B_prompt).replace("G_R", gpt4_response).replace("G_N", str(len(gpt4_prompt.split(" "))))
    # add special prefix and postfix as suggest by Tulu2 official page: https://huggingface.co/allenai/tulu-2-dpo-70b#input-format
    new_prompt = "<|user|>\n" + new_prompt + "<|assistant|>\n"
    
    # ipl data
    w_ipl.write(json.dumps({
        "id": c_id, 
        "prompt": new_prompt,
        "rejected": chatgpt_prompt,
        "chosen": gpt4_prompt,
        "s_p": raw_prompt,
        "r_p": raw_raw_prompt,
        "g_r": gpt4_response,
        "p_o": post_options,
        "case_type": case_type
    }) + "\n")

w_dpo.close()
w_ipl.close()
json.dump(new_data, open("../data/sft_train_data_3W.json", "w"), indent=2)
