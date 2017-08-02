FROM python:3.6.1-alpine3.6

ENV CONAN_VERSION=0.25.1

ADD https://github.com/conan-io/conan/archive/${CONAN_VERSION}.zip /

RUN unzip ${CONAN_VERSION} \
    && rm ${CONAN_VERSION}.zip \
    && cd conan-${CONAN_VERSION} \
    && pip3 install -r conans/requirements.txt \
    && pip3 install -r conans/requirements_server.txt \
    && pip3 install gunicorn

EXPOSE 9300

WORKDIR /conan-${CONAN_VERSION}

COPY entrypoint.sh .

CMD /conan-${CONAN_VERSION}/entrypoint.sh
