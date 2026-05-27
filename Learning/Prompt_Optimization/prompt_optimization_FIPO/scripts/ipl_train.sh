export GLOO_SOCKET_IFNAME=eth0
export WANDB_MODE=disabled

MAXLEN=2048
EPOCH=3
ISLORA=$1  # 1 for lora, 0 for full
SETTING=$2  # ipo or sigmoid
ROOTPATH=$3
BETA=0.01

models=("70b")

for model in "${models[@]}"
    do
    raw_model_path=${ROOTPATH}/model/tulu2-dpo-${model}/
    train_data_path=${ROOTPATH}/data/ipl_train_data_3W.jsonl
    deepspeed_config_path=${ROOTPATH}/data/ds_config.json
    
    # tuning
    for ((i=1; i<=${EPOCH}; i++))
        do

        if [ $i -eq 1 ]
        then
            train_model_path=${raw_model_path}
            train_newdata_path=${train_data_path}
        else
            if  [ $ISLORA -ne 0 ]
            then
                train_newdata_path=${ROOTPATH}/output/ipl-${SETTING}_train_data_3W_$(($i-1))_${model}-lora.jsonl
                train_model_path=${ROOTPATH}/output/tulu2-${model}-ipl-${SETTING}-3W-$(($i-1))-lora/
            else
                train_newdata_path=${ROOTPATH}/output/ipl-${SETTING}_train_data_3W_$(($i-1))_${model}-full.jsonl
                train_model_path=${ROOTPATH}/output/tulu2-${model}-ipl-${SETTING}-3W-$(($i-1))-full/
            fi
        fi

        if  [ $ISLORA -ne 0 ]
        then
            answer_file_path=${ROOTPATH}/output/ipl-${SETTING}_train_data_3W_${i}_${model}-lora.jsonl
            model_output_path=${ROOTPATH}/output/${model}_ipl-${SETTING}_peft_${i}/
            final_model_output_path=${ROOTPATH}/output/tulu2-${model}-ipl-${SETTING}-3W-${i}-lora/
        else
            answer_file_path=${ROOTPATH}/output/ipl-${SETTING}_train_data_3W_${i}_${model}-full.jsonl
            model_output_path=${ROOTPATH}/output/tulu2-${model}-ipl-${SETTING}-3W-${i}-full/
            final_model_output_path=${model_output_path}
        fi

        case ${model} in
            "13b")
                PER_GPU_BATCH=4
                GRA_ACC=4
                ;;
            "70b")
                PER_GPU_BATCH=2
                GRA_ACC=8
                ;;
        esac

        # training
        torchrun --nnodes=$NODE_NUM \
            --node_rank=$INDEX \
            --nproc_per_node $GPU_NUM_PER_NODE \
            --master_addr $MASTER_ADDR \
            --master_port $MASTER_PORT \
            ${ROOTPATH}/codes/train_dpo.py \
            --model_name_or_path ${train_model_path} \
            --bf16 True \
            --output_dir ${model_output_path} \
            --num_train_epochs 1 \
            --per_device_train_batch_size ${PER_GPU_BATCH} \
            --gradient_accumulation_steps ${GRA_ACC} \
            --save_strategy "steps" \
            --save_steps 2500 \
            --save_total_limit 1 \
            --eval_steps 500 \
            --learning_rate 5e-7 \
            --log_level "info" \
            --logging_strategy "steps" \
            --logging_steps 1 \
            --weight_decay 0.05 \
            --warmup_ratio 0.1 \
            --lr_scheduler_type "linear" \
            --deepspeed ${deepspeed_config_path} \
            --tf32 True \
            --model_max_length ${MAXLEN} \
            --train_data_path ${train_newdata_path} \
            --preprocessing_num_workers 32 \
            --dataloader_num_workers 32 \
            --gradient_checkpointing True \
            --report_to "none" \
            --if_lora ${ISLORA} \
            --beta ${BETA} \
            --loss_type ${SETTING}

        # merge lora and base model
        if  [ $ISLORA -ne 0 ]
        then
            python3 ${ROOTPATH}/codes/merge_peft_adapter.py \
                --adapter_model_name ${model_output_path} \
                --base_model_name ${train_model_path} \
                --output_name ${final_model_output_path}
        fi

        # new inference
        if [ $i -ne ${EPOCH} ]
        then
            python3 ${ROOTPATH}/codes/get_model_infer_batch_ipl.py \
                --model-path ${final_model_output_path} \
                --question-file ${train_newdata_path} \
                --answer-file ${answer_file_path} \
                --max-target-len 512 \
                --num-gpus 8 \
                --num-partitions 1 \
                --temperature 0.8 \
                --top-p 0.95
        fi
        done
    done
