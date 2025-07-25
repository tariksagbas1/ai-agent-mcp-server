FROM continuumio/miniconda3

ENV ENV_NAME=icron-llm-env \
    PYTHONUNBUFFERED=1 \
    APP_DIR=/app

# Copy environment file and create environment
COPY environment.yml /tmp/environment.yml
RUN conda env create -f /tmp/environment.yml && conda clean -afy

# Use bash and activate env in script
SHELL ["/bin/bash", "-c"]

WORKDIR $APP_DIR
COPY . $APP_DIR

RUN echo '#!/bin/bash' > /start_service.sh && \
    echo "source activate ${ENV_NAME}" >> /start_service.sh && \
    echo "python ${APP_DIR}/service_core/bootstrap.py --task mcp" >> /start_service.sh && \
    chmod +x /start_service.sh

CMD ["/start_service.sh"]
