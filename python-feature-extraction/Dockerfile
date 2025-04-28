# Use an appropriate Python base image. Add CUDA if needed.
# Example using NVIDIA CUDA base (adjust tags as needed for your CUDA/cuDNN version):
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip ffmpeg libsndfile1 && \
    rm -rf /var/lib/apt/lists/*
# Install system dependencies needed by libraries (e.g., libsndfile for soundfile/librosa, ffmpeg potentially)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg git \ 
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY requirements.txt .

RUN pip install setuptools

RUN pip install torch

RUN pip install numpy

RUN pip install packaging

RUN mkdir ~/pip_build_temp

RUN git clone https://github.com/state-spaces/mamba.git

RUN TMPDIR=~/pip_build_temp MAX_JOBS=4 pip install ./mamba --no-build-isolation

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt 

# Copy source code including generated files
COPY ./src ./src
# Copy proto definitions (optional, only if needed at runtime)
# COPY ./proto ./proto 

# Expose the gRPC port
EXPOSE 50051 

# Command to run the service
# Use -u for unbuffered output, helps with Docker logs
# gRPC message size limits should be configured within the server code (main.py)
CMD ["python", "-u", "-m", "src.server.main"]