# External-validation image: preprocess -> generate reports -> score nodule F1.
#
#   docker build -t ctreportgen-val --build-arg UID=$(id -u) --build-arg GID=$(id -g) .
#   docker run --rm --gpus '"device=0"' \
#     -v $PWD/data:/data:ro -v $HOME/workspace/hf_cache:/hf:ro -v $PWD/out:/out \
#     ctreportgen-val all
#
# Built from the REPOSITORY ROOT, not from inference_bundle/. The bundle arrives as a
# tarball and gets re-extracted whenever a new one lands, which would wipe anything
# added inside it; keeping this file and validation/ outside means an update to the
# bundle costs nothing but a rebuild. inference_bundle/Dockerfile still works on its
# own for a plain inference run and is left untouched.
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

# Host ownership. The defaults match this server's account; pass --build-arg to move
# the image elsewhere. Files under /out are written as this user, so results are
# editable on the host without a chown afterwards.
ARG UID=1001
ARG GID=1001

ENV HF_HOME=/hf \
    HF_HUB_OFFLINE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_ROOT=/data \
    OUT_DIR=/out

RUN groupadd -g "${GID}" infer \
 && useradd -m -u "${UID}" -g "${GID}" infer

WORKDIR /app

# Bundle pins first, then the preprocessing stack, so a change to the validation
# requirements does not invalidate the layer carrying the versions the reported
# numbers were produced with.
COPY inference_bundle/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY validation/requirements.txt ./validation-requirements.txt
RUN pip install --no-cache-dir -r validation-requirements.txt

COPY demo/requirements.txt ./demo-requirements.txt
RUN pip install --no-cache-dir -r demo-requirements.txt

# --chown on the COPY itself: a later `chown -R` would duplicate the 1.3 GB of weights
# into a second image layer.
COPY --chown=infer:infer inference_bundle/src/ ./src/
COPY --chown=infer:infer inference_bundle/run_inference.py .
COPY --chown=infer:infer inference_bundle/weights/ ./weights/
COPY --chown=infer:infer inference_bundle/ject/ ./ject/
COPY --chown=infer:infer validation/ ./validation/
# Live-demo scripts (TC1). Tagged chest-ct-foundation for the demo; see demo/RUNBOOK.md.
COPY --chown=infer:infer demo/ ./demo/

RUN chmod +x ./validation/entrypoint.sh

USER infer
ENTRYPOINT ["/app/validation/entrypoint.sh"]
# Default: the TC1 demo, end to end (demo/run_all.py).
CMD ["demo"]
