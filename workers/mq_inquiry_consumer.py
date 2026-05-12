from __future__ import annotations

import os

import django
import pika

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "carddemo.settings")
django.setup()

from models.account import Account
from services.common.dates import system_date

DATE_REQ = "CARDDEMO.DATE.REQ"
DATE_RESP = "CARDDEMO.DATE.RESP"
ACCT_REQ = "CARDDEMO.ACCT.REQ"
ACCT_RESP = "CARDDEMO.ACCT.RESP"


def main() -> None:
    host = os.getenv("RABBITMQ_HOST", "localhost")
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=host))
    channel = connection.channel()
    for queue in [DATE_REQ, DATE_RESP, ACCT_REQ, ACCT_RESP]:
        channel.queue_declare(queue=queue, durable=True)

    def date_callback(ch, method, _properties, _body):
        ch.basic_publish(exchange="", routing_key=DATE_RESP, body=system_date().encode())
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def account_callback(ch, method, _properties, body):
        acct_id = body.decode().strip()
        account = Account.objects.filter(acct_id=acct_id).first()
        if account:
            payload = f"{account.acct_id},{account.acct_active_status},{account.acct_curr_bal}"
        else:
            payload = "NOTFOUND"
        ch.basic_publish(exchange="", routing_key=ACCT_RESP, body=payload.encode())
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=DATE_REQ, on_message_callback=date_callback)
    channel.basic_consume(queue=ACCT_REQ, on_message_callback=account_callback)
    channel.start_consuming()


if __name__ == "__main__":
    main()
