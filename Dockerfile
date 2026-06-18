# syntax=docker/dockerfile:1
# Multi-stage build: downloads yt-dlp binary and FFmpeg from official builds,
# installs Node.js for EJS support, and keeps the final image small.

# Stage 1: download yt-dlp binary
FROM docker.io/library/alpine:latest AS yt-dlp-bin
ARG YT_DLP_VERSION="2026.06.09"
# Use the glibc-linked binary (yt-dlp_linux) since the python:slim runtime uses glibc.
# For musl-based runtimes (alpine), use yt-dlp_musllinux instead.
RUN wget -O /bin/yt-dlp "https://github.com/yt-dlp/yt-dlp/releases/download/${YT_DLP_VERSION}/yt-dlp_linux" && chmod +x /bin/yt-dlp

# Stage 2: download FFmpeg from yt-dlp's official builds
FROM docker.io/library/alpine:latest AS ffmpeg-bin
RUN APK_ARCH="$(apk --print-arch)" && case "${APK_ARCH}" in x86_64) FILE="ffmpeg-master-latest-linux64-gpl.tar.xz" ;; aarch64) FILE="ffmpeg-master-latest-linuxarm64-gpl.tar.xz" ;; *) echo >&2 "error: unsupported arch: ${APK_ARCH}"; exit 1 ;; esac && wget -O /tmp/ffmpeg.tar.xz "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/${FILE}" && mkdir -p /tmp/ffmpeg && tar -xf /tmp/ffmpeg.tar.xz -C /tmp/ffmpeg --strip-components=1 && mv /tmp/ffmpeg/bin/ffmpeg /tmp/ffmpeg/bin/ffprobe /bin/ && chmod +x /bin/ffmpeg /bin/ffprobe && rm -rf /tmp/ffmpeg /tmp/ffmpeg.tar.xz

# Stage 3: runtime image
FROM docker.io/library/python:3.12-slim

# Install Node.js 24 via nodesource (required by yt-dlp EJS)
RUN apt-get update -qq && apt-get install -y -qq curl ca-certificates gnupg && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && apt-get install -y -qq nodejs && apt-get clean && rm -rf /var/lib/apt/lists/* && node --version

# Copy yt-dlp and FFmpeg from build stages
COPY --from=yt-dlp-bin /bin/yt-dlp /bin/yt-dlp
COPY --from=ffmpeg-bin /bin/ffmpeg /bin/ffprobe /bin/

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && yt-dlp --version && ffmpeg -version | head -1 && node -e "console.log('Node:', process.version)" && python -c "import yt_dlp_ejs; print('yt-dlp-ejs:', yt_dlp_ejs._version)"

COPY . .

RUN yt-dlp -U || true

CMD ["python3", "bot.py"]
