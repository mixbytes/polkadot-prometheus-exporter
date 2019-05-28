# polkadot-prometheus-exporter

Prometheus exporter for Polkadot relay chain node.

Installation
============

via pip
```commandline
pip install polkadot_prometheus_exporter
```

via docker
```commandline
docker pull mixbytes/polkadot-prometheus-exporter
```

Usage
=====

```commandline
usage: polkadot-prometheus-exporter [-h] [--exporter_port EXPORTER_PORT]
                   [--exporter_address EXPORTER_ADDRESS] [--rpc_url RPC_URL]

Prometheus exporter for Polkadot relay chain node

optional arguments:
  -h, --help            show this help message and exit
  --exporter_port EXPORTER_PORT
                        expose metrics on this port
  --exporter_address EXPORTER_ADDRESS
                        expose metrics on this address
  --rpc_url RPC_URL     Polkadot node rpc address
```
