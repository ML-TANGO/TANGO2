export GLOO_SOCKET_IFNAME=eth0
export WANDB_MODE=disabled

finetuned_models=("FIPO-IPL-IPO-Tulu2-70B")
inference_models=("tulu2-dpo-7b")
test_data_types=("generation" "multichoice")
ROOTPATH=$1

# gen test results with new prompts
for finetuned_model in "${finetuned_models[@]}"
    do
    finetuned_model_path=${ROOTPATH}/output/${finetuned_model}/

    for test_data_type in "${test_data_types[@]}"
        do
        case ${test_data_type} in 
            "multichoice")
                ENTRY=${ROOTPATH}/codes/get_model_infer_batch_logits.py
                E_TARLEN=1
                N_LEN=4096
                ;;
            "generation")
                ENTRY=${ROOTPATH}/codes/get_model_infer_batch.py
                E_TARLEN=4096
                N_LEN=4096
                ;;
        esac

        # gen new prompts
        new_prompt_file=${ROOTPATH}/output/${test_data_type}_${finetuned_model}.jsonl
        if [ -f ${new_prompt_file} ]; then
            echo "new prompt file exits"
        else
            python3 ${ROOTPATH}/codes/get_model_infer_batch.py \
                --model-path ${finetuned_model_path} \
                --question-file ${ROOTPATH}/data/test-meta-${test_data_type}-prompt.jsonl \
                --answer-file ${new_prompt_file} \
                --max-target-len ${N_LEN} \
                --num-gpus 8 \
                --num-partitions 1 \
                --temperature 0.8 \
                --top-p 0.95
        fi
        
        # gen test results
        for inference_model in "${inference_models[@]}"
            do
            python3 ${ENTRY} \
                --model-path ${ROOTPATH}/model/tulu2-dpo-${inference_model}/ \
                --question-file ${ROOTPATH}/output/${test_data_type}_${finetuned_model}.jsonl \
                --answer-file ${ROOTPATH}/output/${test_data_type}_${finetuned_model}_${inference_model}.jsonl \
                --max-target-len ${E_TARLEN} \
                --num-gpus 8 \
                --num-partitions 1 \
                --temperature 0.8 \
                --top-p 0.95
            done
        done
    done
