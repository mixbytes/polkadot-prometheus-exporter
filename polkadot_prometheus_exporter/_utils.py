# Copyright (C) 2019  MixBytes, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND (express or implied).

from abc import ABC, abstractmethod
from time import time


class PeriodicTask(ABC):
    """
    Utility class which runs _perform() at most every period_seconds.
    """

    def __init__(self, period_seconds):
        self.period_seconds = period_seconds

        self.__last_invocation_time = None

    @abstractmethod
    def _perform(self):
        raise NotImplementedError()

    def run(self):
        now = time()
        if self.__last_invocation_time is not None and self.__last_invocation_time + self.period_seconds > now:
            return

        self.__last_invocation_time = now
        self._perform()


def check(condition, error_msg=None):
    if not condition:
        raise (RuntimeError() if error_msg is None else RuntimeError(error_msg))
