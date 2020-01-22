#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    brew update || brew update
    brew outdated pyenv || brew upgrade pyenv
    brew install pyenv-virtualenv
    brew install pkg-config
    brew install ninja
    brew install meson

    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi
    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi

    case "${PYVER}" in
        py27)
            pyenv install 2.7.17
            pyenv virtualenv 2.7.17 conan
            ;;
        py35)
            pyenv install 3.5.9
            pyenv virtualenv 3.5.9 conan
            ;;
        py36)
            pyenv install 3.6.10
            pyenv virtualenv 3.6.10 conan
            ;;
        py37)
            pyenv install 3.7.6
            pyenv virtualenv 3.7.6 conan
            ;;
        py38)
            pyenv install 3.8.1
            pyenv virtualenv 3.8.1 conan
            ;;

    esac
    pyenv rehash
    pyenv activate conan
else
    sudo apt-get update
    sudo apt-get install gcc-multilib g++-multilib wget unzip

    wget https://github.com/ninja-build/ninja/releases/download/v1.8.2/ninja-linux.zip
    unzip ninja-linux.zip
    sudo mv ninja /usr/bin/ninja
    rm ninja-linux.zip

    # Will fail if no python3 available
    pip3 install meson || true
fi

pip install -r conans/requirements_dev.txt
pip install -r conans/requirements_server.txt
pip install -r conans/requirements.txt
