FROM ubuntu:14.04

RUN apt-get -y update && apt-get install -y \
    pandoc \
    python2.7 \
    python-pip \
    git \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    python-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY requirements ./requirements

RUN pip install --upgrade pip setuptools
RUN pip install -r /requirements.txt

ENV PYTHONUNBUFFERED 1

RUN mkdir /courselets
WORKDIR /courselets/mysite
