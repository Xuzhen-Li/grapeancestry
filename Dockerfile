# GrapeAncestry v1.0.0 — linux/amd64 customer / lab image skeleton.
# Product fat image grapeancestry:1.0.0 ships privately (panel + VS-1 inside).
# NEVER docker push a fat image that contains panel genotypes.
# Public git build: code + deps only; Analyze cannot finish without private assets.
# ADMIXTURE 1.3.0 is linux x86_64 — do NOT copy a macOS Mach-O from bin/.
# UI: Streamlit 8501 · report server 8502 (see start.sh mounts: /input /output /settings).
FROM mambaorg/micromamba:1.5.8
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        procps wget ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && wget -q -O /tmp/admixture.tgz \
        https://dalexander.github.io/admixture/binaries/admixture_linux-1.3.0.tar.gz \
    && mkdir -p /tmp/admix && tar -xzf /tmp/admixture.tgz -C /tmp/admix \
    && ADMIX_BIN="$(find /tmp/admix -type f -name admixture | head -n1)" \
    && test -n "$ADMIX_BIN" \
    && install -m 0755 "$ADMIX_BIN" /usr/local/bin/admixture \
    && rm -rf /tmp/admixture.tgz /tmp/admix \
    && file /usr/local/bin/admixture || true
USER $MAMBA_USER
WORKDIR /opt/grapeancestry
COPY --chown=$MAMBA_USER:$MAMBA_USER environment-hpc.yml pyproject.toml README.md ./
COPY --chown=$MAMBA_USER:$MAMBA_USER src ./src
COPY --chown=$MAMBA_USER:$MAMBA_USER workflow ./workflow
COPY --chown=$MAMBA_USER:$MAMBA_USER config ./config
COPY --chown=$MAMBA_USER:$MAMBA_USER tests ./tests
COPY --chown=$MAMBA_USER:$MAMBA_USER scripts ./scripts
COPY --chown=$MAMBA_USER:$MAMBA_USER app.py ./
COPY --chown=$MAMBA_USER:$MAMBA_USER docs ./docs
RUN micromamba install -y -n base -f environment-hpc.yml && micromamba clean -a -y
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN pip install -e ".[web]"
ENV PATH=/opt/conda/bin:/usr/local/bin:$PATH
EXPOSE 8501 8502
# Prefer customer drop: docker load -i grapeancestry-v1.0.0-amd64.tar && ./start.sh
# Docs-only build cannot Analyze without mounting private VS-1 + 2449 panel.
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
