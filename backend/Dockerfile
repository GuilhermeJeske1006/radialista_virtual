FROM python:3.12-slim

WORKDIR /app

# ffmpeg: analise de silencio no fim das musicas (app/live/audio_analysis.py) --
# corta antes de trecho falado/silencio longo em vez de tocar o video inteiro.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
