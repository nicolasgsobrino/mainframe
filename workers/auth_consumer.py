from __future__ import annotations

import os

import django
import pika

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "carddemo.settings")
django.setup()

from services.auth_process import parse_auth_request, process_authorization

REQ_QUEUE = "CARDDEMO.AUTH.REQ"
RESP_QUEUE = "CARDDEMO.AUTH.RESP"


def main() -> None:
    host = os.getenv("RABBITMQ_HOST", "localhost")
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=host))
    channel = connection.channel()
    channel.queue_declare(queue=REQ_QUEUE, durable=True)
    channel.queue_declare(queue=RESP_QUEUE, durable=True)

    def callback(ch, method, _properties, body):
        response = process_authorization(parse_auth_request(body))
        ch.basic_publish(exchange="", routing_key=RESP_QUEUE, body=response.encode("latin-1"))
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=REQ_QUEUE, on_message_callback=callback)
    channel.start_consuming()


if __name__ == "__main__":
    main()
