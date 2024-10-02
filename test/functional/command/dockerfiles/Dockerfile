FROM ubuntu:22.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        python3 \
        python3-pip \
        python3-venv \
        sudo \
    && rm -rf /var/lib/apt/lists/*

ARG DOCKER_GID=127

RUN groupadd -g $DOCKER_GID docker || groupmod -g $DOCKER_GID docker

RUN usermod -aG docker root

COPY . /root/conan-io
RUN cd /root/conan-io && pip install -e .
