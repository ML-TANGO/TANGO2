export GLOO_SOCKET_IFNAME=eth0
export WANDB_MODE=disabled

MAXLEN=2048
ISLORA=$1  # 1 for lora, 0 for full
ROOTPATH=$2
EPOCH=3

models=("70b")

for model in "${models[@]}"
    do
    raw_model_path=${ROOTPATH}/model/tulu2-dpo-${model}/
    train_data_path=${ROOTPATH}/data/sft_train_data_3W.json
    deepspeed_config_path=${ROOTPATH}/data/ds_config.json

    if [ $ISLORA -ne 0 ]
    then
        model_output_path=${ROOTPATH}/output/tulu2-${model}-sft_peft/
        final_model_output_path=${ROOTPATH}/output/tulu2-${model}-sft-3W-lora/
    else
        model_output_path=${ROOTPATH}/output/tulu2-${model}-sft-3W-full/
    fi

    case ${model} in 
        "13b")
            if [ $ISLORA -ne 0 ]
            then
                PER_GPU_BATCH=16
                GRA_ACC=1
            else
                PER_GPU_BATCH=8
                GRA_ACC=2
            fi
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
        ${ROOTPATH}/codes/train_sft.py \
        --model_name_or_path ${raw_model_path} \
        --bf16 True \
        --output_dir ${model_output_path} \
        --num_train_epochs ${EPOCH} \
        --per_device_train_batch_size ${PER_GPU_BATCH} \
        --gradient_accumulation_steps ${GRA_ACC} \
        --save_strategy "steps" \
        --save_steps 1500 \
        --save_total_limit 1 \
        --learning_rate 2e-5 \
        --log_level "info" \
        --logging_strategy "steps" \
        --logging_steps 1 \
        --weight_decay 0. \
        --warmup_ratio 0.04 \
        --lr_scheduler_type "cosine" \
        --deepspeed ${deepspeed_config_path} \
        --tf32 True \
        --model_max_length ${MAXLEN} \
        --train_data_path ${train_data_path} \
        --preprocessing_num_workers 1 \
        --gradient_checkpointing True \
        --report_to "none"

    if  [ $ISLORA -ne 0 ]
    then
        # merge lora and base model
        python3 ${ROOTPATH}/codes/merge_peft_adapter.py \
            --adapter_model_name ${model_output_path} \
            --base_model_name ${raw_model_path} \
            --output_name ${final_model_output_path}
    fi
    done
