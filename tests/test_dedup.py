"""Tests para deduplicacion de mensajes WhatsApp."""

from openagno.core.dedup import MessageDeduplicator


def test_message_deduplicator_ignores_repeated_id():
    dedup = MessageDeduplicator(ttl=60, max_size=10)
    assert dedup.is_duplicate("wamid-1") is False
    assert dedup.is_duplicate("wamid-1") is True


def test_message_deduplicator_evicts_oldest_when_full():
    dedup = MessageDeduplicator(ttl=60, max_size=2)
    assert dedup.is_duplicate("a") is False
    assert dedup.is_duplicate("b") is False
    assert dedup.is_duplicate("c") is False
    assert "a" not in dedup._cache
