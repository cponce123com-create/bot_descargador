FROM python:3.12-slim

# Instalar Deno (runtime JavaScript requerido por yt-dlp desde 2025.11.12)
RUN apt-get update -qq && apt-get install -y -qq curl ffmpeg > /dev/null && 
    curl -fsSL https://deno.land/install.sh | sh && 
    mv /root/.deno/bin/deno /usr/local/bin/deno && 
    rm -rf /root/.deno && 
    apt-get remove -y curl && apt-get autoremove -y && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "bot.py"]
