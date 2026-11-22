"""Laço asyncio em uma thread de fundo."""

import asyncio
import threading
from typing import Any, Coroutine


class BackgroundLoop:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="assistente-loop", daemon=True)
        self.thread.start()

    def run(self, coroutine: Coroutine, timeout: float = 300) -> Any:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout)
