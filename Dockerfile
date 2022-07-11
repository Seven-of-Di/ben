FROM continuumio/miniconda3

# RUN apt update && apt upgrade -y
# RUN apt install -y \
#   build-essential \
#   zlib1g-dev \
#   libncurses5-dev \
#   libgdbm-dev \
#   libnss3-dev \
#   libssl-dev \
#   libreadline-dev \
#   libffi-dev \
#   libsqlite3-dev \
#   wget \
#   libbz2-dev

# ENV PYTHON_VERSION 3.7.13
# RUN cd /tmp && wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz 
# RUN cd /tmp && tar -xzf Python-${PYTHON_VERSION}.tgz

# RUN cd /tmp/Python-${PYTHON_VERSION} && ./configure && make && make altinstall

# RUN apt install -y python3-pip

# RUN cd /tmp \
#     && wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
#     && mkdir /root/.conda \
#     && bash Miniconda3-latest-Linux-x86_64.sh -b \
#     && rm -f Miniconda3-latest-Linux-x86_64.sh 

# ENV PATH="/root/miniconda3/bin:${PATH}"

RUN mkdir -p /app

WORKDIR /app

COPY environment.yml .

RUN conda env create -f ./environment.yml

RUN echo "conda activate ben" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]

COPY ./docker/entrypoint.sh /entrypoint.sh

COPY . .
WORKDIR /app/src

ENTRYPOINT [ "/entrypoint.sh"]
