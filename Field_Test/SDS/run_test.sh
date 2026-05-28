# Standard single-channel processing
python3 generate_reports.py \
    --checkpoint models/pytorch_model.bin \
    --input_dir /input/ \
    --impressions_emb models/impression_embeddings.pth \
    --findings_emb models/findings_embeddings.pth \
    --output_path /output/results.json