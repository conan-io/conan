FROM ubuntu:latest

LABEL maintainer="Conan.io <info@conan.io>"

ARG DEBIAN_FRONTEND=noninteractive
ENV PY38 3.8.6
ENV PYENV_ROOT="/home/runner/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"

# Install essential packages and dependencies for pyenv and other tools
RUN apt-get -qq update \
    && apt-get -qq install -y --no-install-recommends \
       sudo ca-certificates \
       make build-essential libssl-dev zlib1g-dev libbz2-dev \
       libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev \
       xz-utils tk-dev libffi-dev liblzma-dev git \
       adduser \
    && rm -rf /var/lib/apt/lists/*


# Create the 'runner' user
RUN adduser --disabled-password --gecos "" --uid 1001 runner \
    && usermod -aG sudo runner

# Set up pyenv environment and install Python version
RUN curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash \
    && export PATH="$PYENV_ROOT/bin:$PATH" \
    && eval "$(pyenv init --path)" \
    && pyenv install $PY38 \
    && pyenv global $PY38 \
    && python -m ensurepip --upgrade \
    && chown -R runner:runner /home/runner/.pyenv




# Clean up unnecessary packages
RUN apt-get -qq remove make build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# Set up the work directory for the runner user
WORKDIR /home/runner

# Switch to the runner user
USER runner

# Ensure pyenv is available for the runner user
RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> /home/runner/.bashrc \
    && echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> /home/runner/.bashrc \
    && echo 'eval "$(pyenv init --path)"' >> /home/runner/.bashrc \
    && echo 'eval "$(pyenv init -)"' >> /home/runner/.bashrc
