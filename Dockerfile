FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 10000 8501
# Render overrides the Docker command through render.yaml; local default remains Streamlit.
CMD ["sh", "-c", "streamlit run app/ui.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]
