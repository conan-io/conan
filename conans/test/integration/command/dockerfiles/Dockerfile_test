FROM ubuntu
RUN apt update && apt upgrade -y
RUN apt install -y build-essential
RUN apt install -y python3-pip cmake git build-essential
RUN pip install docker
COPY . /root/conan-io
RUN cd /root/conan-io && pip install -e .