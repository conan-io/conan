#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    brew update || brew update
    brew outdated pyenv || brew upgrade pyenv
    brew install pyenv-virtualenv

    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi
    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi

    case "${PYVER}" in
        py27)
            pyenv install 2.7.10
            pyenv virtualenv 2.7.10 conan
            ;;
        py33)
            pyenv install 3.3.6
            pyenv virtualenv 3.3.6 conan
            ;;
        py34)
            pyenv install 3.4.3
            pyenv virtualenv 3.4.3 conan
            ;;
        py35)
            pyenv install 3.5.0
            pyenv virtualenv 3.5.0 conan
            ;;
        py36)
            pyenv install 3.6.0
            pyenv virtualenv 3.6.0 conan
            ;;

    esac
    pyenv rehash
    pyenv activate conan
else
    sudo apt-get update
    sudo apt-get install gcc-multilib g++-multilib
fi

pip install -r conans/requirements_dev.txt
pip install -r conans/requirements_server.txt
pip install -r conans/requirements.txt
