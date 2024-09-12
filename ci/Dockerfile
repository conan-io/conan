FROM ubuntu:latest

LABEL maintainer="Conan.io <info@conan.io>"

RUN apt-get update && apt-get install -y \
    git \
    curl \
    make \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
    python3-openssl \
    ca-certificates \
    sudo

RUN useradd -m -s /bin/bash conan && \
    echo 'conan ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER conan
WORKDIR /home/conan
ENV PATH /home/conan/.pyenv/shims:/home/conan/.pyenv/bin:$PATH

RUN curl https://pyenv.run | bash

RUN echo 'export PATH="/home/conan/.pyenv/bin:$PATH"' >> /home/conan/.bashrc && \
    echo 'eval "$(pyenv init --path)"' >> /home/conan/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> /home/conan/.bashrc && \
    echo 'eval "$(pyenv virtualenv-init -)"' >> /home/conan/.bashrc

RUN /bin/bash -c "source /home/conan/.bashrc && pyenv install 3.8.6 && pyenv global 3.8.6"

CMD ["/bin/bash"]
