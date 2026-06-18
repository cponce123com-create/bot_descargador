FROM python:3.12-slim

RUN apt-get update -qq && apt-get install -y -qq ffmpeg curl unzip && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deno.land/install.sh | sh && mv /root/.deno/bin/deno /usr/local/bin/deno && rm -rf /root/.deno && deno --version

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN yt-dlp --version && python -c "import yt_dlp_ejs; print('yt-dlp-ejs:', yt_dlp_ejs._version)" && deno eval "console.log('Deno OK')"

COPY . .

RUN yt-dlp -U || true

CMD ["python3", "bot.py"]
