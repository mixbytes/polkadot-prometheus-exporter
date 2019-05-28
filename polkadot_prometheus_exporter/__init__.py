# Prometheus exporter for Polkadot relay chain node

# Copyright (C) 2019  MixBytes, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND (express or implied).

# TODO WebSocket subscriptions

import sys
import os
from time import sleep, time
from signal import signal, SIGINT, SIGTERM
import argparse

from prometheus_client import start_http_server, Counter, Gauge

if __name__ == '__main__':
    # have to make sure we'll be able to find submodules
    sys.path.append(os.path.realpath(os.path.dirname(os.path.dirname(__file__))))

from polkadot_prometheus_exporter._utils import check
from polkadot_prometheus_exporter._rpc import PolkadotRPC, PolkadotRPCError, get_block_num
from polkadot_prometheus_exporter._blockchain import BlockCache
from polkadot_prometheus_exporter._tasks import SystemInfoUpdater, HealthInfoUpdater, MemPoolUpdater, \
    FinalityInfoUpdater


class Exporter:
    """
    The main exporter logic ties together metrics retrieval and metrics export.
    """

    POLL_INTERVAL = 0.5

    def __init__(self, exporter_port, exporter_address='', rpc_url='http://127.0.0.1:9933/'):
        self.exporter_port = exporter_port
        self.exporter_address = exporter_address

        self._rpc = PolkadotRPC(rpc_url)

        self._last_processed_block_num = None
        self._last_processed_block_hash = None

        self._block_cache = BlockCache(self._rpc)

        self._gauge_highest_block = Gauge('polkadot_highest_block',
                                          'Number of the highest block in chain as seen by current node')
        self._counter_blocks_seen = Counter('polkadot_blocks',
                                            'Number of blocks received by current node')
        self._counter_extrinsics_seen = Counter('polkadot_extrinsics',
                                                'Number of extrinsics received by current node')

        self._info_updaters = [SystemInfoUpdater(self._rpc), HealthInfoUpdater(self._rpc),
                               MemPoolUpdater(self._rpc), FinalityInfoUpdater(self._rpc, self._block_cache)]

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
            except PolkadotRPCError:
                pass

            delay = next_iteration_time - time()
            if delay > 0:
                sleep(delay)

    def _step(self):
        self._run_updaters()

        # optimization
        latest_block_hash = self._rpc.request('chain_getBlockHash')['result']
        if self._last_processed_block_hash is not None and latest_block_hash == self._last_processed_block_hash:
            return

        latest_block = self._block_cache.get(latest_block_hash)

        latest_block_num = get_block_num(latest_block)
        self._gauge_highest_block.set(latest_block_num)

        while self._last_processed_block_num is None or self._last_processed_block_num < latest_block_num:
            if self._last_processed_block_num is None:
                block = latest_block
            else:
                block_hash = self._rpc.request('chain_getBlockHash', [self._last_processed_block_num + 1])['result']
                check(block_hash is not None, 'hash of {} must not be none'.format(self._last_processed_block_num + 1))

                # optimization
                self._last_processed_block_hash = block_hash

                block = self._block_cache.get(block_hash)
                check(block is not None, 'block {} must not be none'.format(self._last_processed_block_num + 1))

            self._counter_blocks_seen.inc()
            self._last_processed_block_num = get_block_num(block)

            self._counter_extrinsics_seen.inc(len(block['block']['extrinsics']))

            self._run_updaters()

    def _run_updaters(self):
        for updater in self._info_updaters:
            updater.run()


def main():
    ap = argparse.ArgumentParser(description='Prometheus exporter for Polkadot relay chain node')
    ap.add_argument("--exporter_port", type=int, default=8000, help='expose metrics on this port')
    ap.add_argument("--exporter_address", type=str, help='expose metrics on this address')
    ap.add_argument("--rpc_url", type=str, default='http://127.0.0.1:9933/', help='Polkadot node rpc address')

    args = ap.parse_args()
    Exporter(args.exporter_port, args.exporter_address if args.exporter_address else '', args.rpc_url).serve_forever()


if __name__ == '__main__':
    main()
