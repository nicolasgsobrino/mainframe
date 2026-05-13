from __future__ import annotations

import logging
import os

import django
import pika

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "carddemo.settings")
django.setup()

from services.auth_process import parse_auth_request, process_authorization  # noqa: E402

REQ_QUEUE = "CARDDEMO.AUTH.REQ"
RESP_QUEUE = "CARDDEMO.AUTH.RESP"
LOGGER = logging.getLogger(__name__)


def handle_authorization_message(ch, method, body) -> None:
    try:
        response = process_authorization(parse_auth_request(body))
    except Exception:
        LOGGER.exception("Failed to process authorization request")
        response = f"{'':<16}{'':<15}{'PYAUTH':<6}{'96':<2}{'ERR':<4}{0:+013.2f}"
    finally:
        try:
            ch.basic_publish(
                exchange="",
                routing_key=RESP_QUEUE,
                body=response.encode("latin-1"),
                properties=pika.BasicProperties(delivery_mode=2),
            )
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    host = os.getenv("RABBITMQ_HOST", "localhost")
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=host))
    channel = connection.channel()
    channel.queue_declare(queue=REQ_QUEUE, durable=True)
    channel.queue_declare(queue=RESP_QUEUE, durable=True)

    def callback(ch, method, _properties, body):
        handle_authorization_message(ch, method, body)

    channel.basic_consume(queue=REQ_QUEUE, on_message_callback=callback)
    channel.start_consuming()


if __name__ == "__main__":
    main()
