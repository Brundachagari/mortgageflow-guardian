# Container image for the MortgageFlow Guardian dashboard.
#
# The core pipeline is serverless (AWS Lambda) and doesn't need a container.
# The Streamlit dashboard, though, is a standalone web app -- containerizing it
# makes it portable: the same image runs on a laptop, ECS, or Kubernetes.
#
# Build:  docker build -t mortgageflow-dashboard .
# Run:    docker run -p 8501:8501 mortgageflow-dashboard
#         (add  -e ANTHROPIC_API_KEY=sk-ant-...  to enable the real Claude toggle)
# Open:   http://localhost:8501

FROM python:3.12-slim

# Keep Python lean and unbuffered so logs stream immediately.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the dashboard needs to run.
COPY src ./src
COPY dashboard.py .
COPY sample_documents ./sample_documents
COPY .streamlit ./.streamlit

# Streamlit's default port.
EXPOSE 8501

# A simple healthcheck so orchestrators (ECS/K8s) know the app is up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Bind to 0.0.0.0 so the container is reachable from outside.
CMD ["streamlit", "run", "dashboard.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
