FROM continuumio/miniconda3

RUN mkdir -p /app

WORKDIR /app

COPY environment.yml .

RUN conda env create -f ./environment.yml

RUN echo "conda activate ben" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]

COPY requirements.txt .

RUN apt-get update \
  && apt-get install -y build-essential
RUN pip install -r requirements.txt

COPY ./docker/entrypoint.sh /entrypoint.sh

COPY . .

WORKDIR /app/src

ENTRYPOINT [ "/entrypoint.sh"]
