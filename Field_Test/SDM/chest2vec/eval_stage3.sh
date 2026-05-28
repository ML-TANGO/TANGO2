python3 eval_stage3_section.py \
  --pretrained lukeingawesome/chest2vec_0.6b_chest \
  --use_chest2vec_loader \
  --pooler_dir /opt/project/ctencoder/chest2vec/runs/stage3_ct_anatomy_0.6b_noinstruct/checkpoint-344 \
  --df final_ct2_exist_section.csv \
  --split val \
  --max_len_query 512 \
  --max_len_section 512 \
  --embed_bs 16 \
  --ks 1,5,10 \
  --device cuda:0 \
  --save_metrics_csv chest2vec/runs/stage3_ct_anatomy_0.6b_noinstruct/test_metrics0.6b.csv \
  --findings_col findings

