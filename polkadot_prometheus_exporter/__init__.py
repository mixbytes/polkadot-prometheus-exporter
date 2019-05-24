# Prometheus exporter for Polkadot relay chain node

# Copyright (C) 2019  MixBytes, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND (express or implied).

import json
from time import sleep, time
from signal import signal, SIGINT, SIGTERM
import argparse

from requests.exceptions import RequestException
import requests
from prometheus_client import start_http_server, Counter, Gauge, Info


class _PolkadotRPCError(RuntimeError):
    pass


class _PolkadotRPC:
    """
    Class interacts with a Polkadot node via RPC and takes care of errors.
    """

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url

        self._next_id = 1

        self._counter_rpc_calls = Counter('polkadot_exporter_rpc_calls', 'Total number of RPC calls made by metric exporter')

        self._counter_network_error = Counter('polkadot_exporter_rpc_network_error', 'RPC connectivity errors')
        self._counter_unexpected_status = Counter('polkadot_exporter_rpc_unexpected_status',
                                                  'RPC call unexpected HTTP status errors')
        self._counter_4xx_error = Counter('polkadot_exporter_rpc_4xx_error', 'RPC call HTTP 4xx errors')
        self._counter_5xx_error = Counter('polkadot_exporter_rpc_5xx_error', 'RPC call HTTP 5xx errors')

        self._counter_request_error = Counter('polkadot_exporter_rpc_error', 'RPC calls declined by Polkadot node')

    def request_nothrow(self, method, params=None):
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": [] if params is None else params,
            "id": self._next_id
        }
        self._next_id += 1

        self._counter_rpc_calls.inc()
        try:
            result = requests.request("POST", self.rpc_url, data=json.dumps(request),
                                      headers={'content-type': 'application/json'})
        except RequestException:
            # TODO more fine-grained error handling
            self._counter_network_error.inc()
            return

        if result.status_code != 200:
            if 400 <= result.status_code < 500:
                self._counter_4xx_error.inc()
            elif 500 <= result.status_code < 600:
                self._counter_5xx_error.inc()
            else:
                self._counter_unexpected_status.inc()

            return

        result_json = result.json()
        if result_json.get('error'):
            self._counter_request_error.inc()
            return

        return result_json

    def request(self, method, params=None):
        result = self.request_nothrow(method, params)

        if result is None:
            raise _PolkadotRPCError()

        return result


class Exporter:
    """
    The main exporter logic ties together metrics retrieval and metrics export.
    """

    POLL_INTERVAL = 0.5

    def __init__(self, exporter_port, exporter_address='', rpc_url='http://127.0.0.1:9933/'):
        self.exporter_port = exporter_port
        self.exporter_address = exporter_address

        self._rpc = _PolkadotRPC(rpc_url)

        self._last_processed_block_num = None
        self._last_processed_block_hash = None

        self._gauge_highest_block = Gauge('polkadot_highest_block',
                                          'Number of the highest block in chain as seen by current node')
        self._counter_blocks_seen = Counter('polkadot_blocks',
                                            'Number of blocks received by current node')
        self._counter_extrinsics_seen = Counter('polkadot_extrinsics',
                                                'Number of extrinsics received by current node')

    def serve_forever(self):
        start_http_server(self.exporter_port, self.exporter_address)

        stop = [False]

        def set_stop(_number, _frame):
            stop[0] = True

        signal(SIGINT, set_stop)
        signal(SIGTERM, set_stop)

        while not stop[0]:
            next_iteration_time = time() + self.__class__.POLL_INTERVAL

            try:
                self._step()
            except _PolkadotRPCError:
                pass

            delay = next_iteration_time - time()
            if delay > 0:
                sleep(delay)

    def _step(self):
        # optimization
        if (self._last_processed_block_hash is not None
                and self._rpc.request('chain_getBlockHash')['result'] == self._last_processed_block_hash):
            return

        latest_block = self._rpc.request('chain_getBlock')

        latest_block_num = _get_block_num(latest_block)
        self._gauge_highest_block.set(latest_block_num)

        while self._last_processed_block_num is None or self._last_processed_block_num < latest_block_num:
            if self._last_processed_block_num is None:
                block = latest_block
            else:
                block_hash = self._rpc.request('chain_getBlockHash', [self._last_processed_block_num + 1])['result']
                _check(block_hash is not None, 'hash of {} must not be none'.format(self._last_processed_block_num + 1))

                # optimization
                self._last_processed_block_hash = block_hash

                block = self._rpc.request('chain_getBlock', [block_hash])
                _check(block is not None, 'block {} must not be none'.format(self._last_processed_block_num + 1))

            self._counter_blocks_seen.inc()
            self._last_processed_block_num = _get_block_num(block)

            self._counter_extrinsics_seen.inc(len(block['result']['block']['extrinsics']))


def _get_block_num(rpc_block):
    return int(rpc_block['result']['block']['header']['number'], 16)


def _check(condition, error_msg=None):
    if not condition:
        raise (RuntimeError() if error_msg is None else RuntimeError(error_msg))


def main():
    ap = argparse.ArgumentParser(description='Prometheus exporter for Polkadot relay chain node')
    ap.add_argument("--exporter_port", type=int, default=8000, help='expose metrics on this port')
    ap.add_argument("--exporter_address", type=str, help='expose metrics on this address')
    ap.add_argument("--rpc_url", type=str, default='http://127.0.0.1:9933/', help='Polkadot node rpc address')

    args = ap.parse_args()
    Exporter(args.exporter_port, args.exporter_address if args.exporter_address else '', args.rpc_url).serve_forever()


if __name__ == '__main__':
    main()
