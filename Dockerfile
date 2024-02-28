FROM ubuntu

RUN apt update && apt upgrade -y
RUN apt install -y build-essential
RUN apt install -y python3-pip cmake
RUN pip3 install conan
ADD . /root/conan-io
RUN cd /root/conan-io && pip install -e .
