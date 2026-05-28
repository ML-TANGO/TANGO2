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
    train_data_path=${ROOTPATH}/data/dpo_train_data_3W.jsonl
    deepspeed_config_path=${ROOTPATH}/data/ds_config.json

    if [ $ISLORA -ne 0 ]
    then
        model_output_path=${ROOTPATH}/output/${model}_${SETTING}_peft/
        final_model_output_path=${ROOTPATH}/output/tulu2-${model}-${SETTING}-3W-lora/
    else
        model_output_path=${ROOTPATH}/output/tulu2-${model}-${SETTING}-3W-full/
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
        --model_name_or_path ${raw_model_path} \
        --bf16 True \
        --output_dir ${model_output_path} \
        --num_train_epochs ${EPOCH} \
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
        --train_data_path ${train_data_path} \
        --preprocessing_num_workers 32 \
        --dataloader_num_workers 32 \
        --gradient_checkpointing True \
        --report_to "none" \
        --if_lora ${ISLORA} \
        --beta ${BETA} \
        --loss_type ${SETTING}

    if  [ $ISLORA -ne 0 ]
    then
        # merge lora and base model
        python3 ${ROOTPATH}/codes/merge_peft_adapter.py \
            --adapter_model_name ${model_output_path} \
            --base_model_name ${raw_model_path} \
            --output_name ${final_model_output_path}
    fi
    done
