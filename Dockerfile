FROM python:3.6-alpine
MAINTAINER Eenae <alexey@mixbytes.io>

WORKDIR /src
COPY . /src
RUN pip install --no-cache-dir -r requirements.txt \
    && python setup.py install
WORKDIR /
ENTRYPOINT ["polkadot-prometheus-exporter"]