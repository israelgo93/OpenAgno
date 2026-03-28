"""Runtime helpers for low-overhead message deduplication."""

from __future__ import annotations

import time
from collections import OrderedDict


class MessageDeduplicator:
	"""TTL + LRU cache para ignorar mensajes ya vistos sin costo significativo."""

	def __init__(self, ttl: int = 60, max_size: int = 1000):
		self.ttl = ttl
		self.max_size = max_size
		self._cache: OrderedDict[str, float] = OrderedDict()

	def _prune(self, now: float) -> None:
		while self._cache:
			oldest_key, oldest_seen_at = next(iter(self._cache.items()))
			if now - oldest_seen_at <= self.ttl:
				break
			self._cache.pop(oldest_key, None)

		while len(self._cache) >= self.max_size:
			self._cache.popitem(last=False)

	def is_duplicate(self, message_id: str) -> bool:
		if not message_id:
			return False

		now = time.time()
		self._prune(now)

		if message_id in self._cache:
			self._cache.move_to_end(message_id)
			return True

		self._cache[message_id] = now
		return False
