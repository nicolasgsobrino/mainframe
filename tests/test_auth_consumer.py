from __future__ import annotations

from types import SimpleNamespace

import workers.auth_consumer as auth_consumer


class FakeChannel:
    def __init__(self) -> None:
        self.published = []
        self.acked = []

    def basic_publish(self, **kwargs) -> None:
        self.published.append(kwargs)

    def basic_ack(self, **kwargs) -> None:
        self.acked.append(kwargs)


def test_auth_consumer_publishes_persistent_response_and_acks(monkeypatch):
    channel = FakeChannel()
    method = SimpleNamespace(delivery_tag=123)
    monkeypatch.setattr(auth_consumer, "parse_auth_request", lambda body: body)
    monkeypatch.setattr(auth_consumer, "process_authorization", lambda request: "OK")

    auth_consumer.handle_authorization_message(channel, method, b"request")

    assert channel.published[0]["routing_key"] == auth_consumer.RESP_QUEUE
    assert channel.published[0]["body"] == b"OK"
    assert channel.published[0]["properties"].delivery_mode == 2
    assert channel.acked == [{"delivery_tag": 123}]


def test_auth_consumer_acks_and_returns_error_on_parse_failure(monkeypatch):
    channel = FakeChannel()
    method = SimpleNamespace(delivery_tag=456)

    def fail_parse(_body):
        raise ValueError("bad payload")

    monkeypatch.setattr(auth_consumer, "parse_auth_request", fail_parse)

    auth_consumer.handle_authorization_message(channel, method, b"bad")

    assert channel.published[0]["body"][31:37].strip() == b"PYAUTH"
    assert channel.published[0]["properties"].delivery_mode == 2
    assert channel.acked == [{"delivery_tag": 456}]
