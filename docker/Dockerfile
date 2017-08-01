FROM python:3.6.1-alpine3.6

ENV CONAN_VERSION=0.25.1

RUN apk add —no-cache git

RUN cd / \
    && git clone https://github.com/conan-io/conan.git \
    && cd conan \
    && git checkout $CONAN_VERSION \
    && pip3 install -r conans/requirements.txt \
    && pip3 install -r conans/requirements_server.txt \
    && pip3 install gunicorn

EXPOSE 9300

VOLUME /root/.conan_server

WORKDIR /conan

ENTRYPOINT gunicorn -b 0.0.0.0:9300 -w 4 -t 300 conans.server.server_launcher:app
