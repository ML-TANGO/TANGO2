# Interactive demo GUI: chest CT (DICOM / NIfTI) in, structured report out.
#
#   docker build -t chest-ct-gui:1 .          (from chestct_foundation/gui/)
#   ../run_gui.sh                             (see README.md)
#
# Built ON TOP of the verified TC1 image, so the model code, weights and the pinned
# inference stack are exactly the ones TC1 measured; that image itself is untouched.
FROM chest-ct-foundation:tc1

USER root
# Every package already in the base is pinned, so adding the GUI stack cannot move
# torch / transformers / peft / numpy under the model.
RUN pip freeze | grep -v ' @ ' > /tmp/base-constraints.txt \
 && pip install --no-cache-dir -c /tmp/base-constraints.txt \
      TotalSegmentator==2.18.0 gradio==6.30.0 SimpleITK==2.5.6 \
 && rm /tmp/base-constraints.txt

# TotalSegmentator weights baked in: the container needs no internet for segmentation,
# and usage statistics are switched off (nothing about the scan leaves the server).
ENV TOTALSEG_HOME_DIR=/opt/totalseg
RUN mkdir -p /opt/totalseg \
 && totalseg_download_weights -t total \
 && python3 -c "import json; json.dump({'totalseg_id': 'offline', 'send_usage_stats': False, 'statistics_disclaimer_shown': True, 'prediction_counter': 0}, open('/opt/totalseg/config.json', 'w'))" \
 && chown -R infer:infer /opt/totalseg

# Gradio keeps its share-link tunnel client (frpc) under HF_HOME, which in the base image
# is the read-only model mount. Move HF_HOME to a writable folder, keep the model cache
# where it is, and fetch frpc at build time (Gradio's downloader checks its sha256).
ENV HF_HOME=/opt/hf_home HF_HUB_CACHE=/hf/hub
RUN mkdir -p /opt/hf_home \
 && python3 -c "from gradio.tunneling import Tunnel; Tunnel.download_binary()" \
 && ls -l /opt/hf_home/gradio/frpc \
 && chown -R infer:infer /opt/hf_home

# Uploads and intermediate files live here, inside the container: removed with it.
RUN mkdir -p /work && chown infer:infer /work

COPY --chown=infer:infer app/ /app/gui/

USER infer
WORKDIR /app/gui
EXPOSE 7860
ENTRYPOINT ["python3", "/app/gui/app.py"]
