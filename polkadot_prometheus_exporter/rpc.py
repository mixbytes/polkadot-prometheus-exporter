# Copyright (C) 2019  MixBytes, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND (express or implied).

import json

from requests.exceptions import RequestException
import requests
from prometheus_client import Counter


class PolkadotRPCError(RuntimeError):
    pass


class PolkadotRPC:
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
            raise PolkadotRPCError()

        return result


def get_block_num(rpc_block):
    return int(rpc_block['block']['header']['number'], 16)
