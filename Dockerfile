FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-client \
        libpq-dev \
        gcc \
        python3-dev \
        ffmpeg \
        git \
        libegl1 \
        libgles2 \
        libgl1 \
        libgl1-mesa-dri \
        libgomp1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    # pyrender pins PyOpenGL==3.1.0 (numpy-2 incompatible, crashes in glGenTextures);
    # upgrade it to a numpy-2-compatible release. --no-deps avoids re-resolving
    # against pyrender's hard pin.
    pip install --no-cache-dir --upgrade --no-deps "PyOpenGL==3.1.10"

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Set Python path
ENV PYTHONPATH=/app
# Offscreen OpenGL rendering (EGL + Mesa llvmpipe) for GLB thumbnails
ENV PYOPENGL_PLATFORM=egl

# Copy and set up startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Run startup script
CMD ["./start.sh"]
