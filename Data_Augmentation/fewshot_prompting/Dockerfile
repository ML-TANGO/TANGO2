# Few-Shot Prompt Optimization service — Tango MSA backend.
# CPU-only is sufficient: this service does NOT host a model. It calls a
# remote OpenAI-compatible LLM endpoint (llm_url) supplied per request.
#
# metric="spice" (the default) runs a Java SPICE server: the image carries a
#   Java 8 runtime and the SPICE jars; Stanford CoreNLP (~370 MB) is downloaded
#   when the container starts.
# WITH_BERTSCORE=true also enables metric="bert_score" with CPU-only PyTorch;
#   the BERTScore model is likewise downloaded at start-up.

# --- SPICE: jars from the pycocoevalcap wheel + the compiled SpiceServer -----
FROM python:3.10-slim AS spice-jars
COPY spice/fetch_jars.py /tmp/
RUN python /tmp/fetch_jars.py /opt/spice

FROM eclipse-temurin:8-jdk-jammy AS spice-server
COPY --from=spice-jars /opt/spice/spice-1.0.jar /opt/spice/
COPY spice/SpiceServer.java /tmp/
RUN mkdir -p /opt/spice/server && \
    javac -classpath /opt/spice/spice-1.0.jar -d /opt/spice/server /tmp/SpiceServer.java

FROM eclipse-temurin:8-jre-jammy AS java

# --- service ------------------------------------------------------------------
FROM python:3.10-slim

ARG WITH_BERTSCORE=false

ENV PYTHONUNBUFFERED=1 \
    PORT=30000 \
    JAVA_HOME=/opt/java/openjdk \
    PATH=/opt/java/openjdk/bin:$PATH \
    SPICE_HOME=/opt/spice

WORKDIR /app

COPY --from=java /opt/java/openjdk /opt/java/openjdk
COPY --from=spice-jars /opt/spice /opt/spice
COPY --from=spice-server /opt/spice/server /opt/spice/server

# Dependencies first (build-cache friendly).
COPY requirements.txt requirements-bertscore.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    if [ "$WITH_BERTSCORE" = "true" ]; then \
        pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu && \
        pip install --no-cache-dir -r requirements-bertscore.txt; \
    fi

# Service code.
COPY . .

# Must match values.yaml backend.port (Tango MSA 탑재 가이드).
EXPOSE 30000

# /health, /info, /run on :30000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "30000"]
