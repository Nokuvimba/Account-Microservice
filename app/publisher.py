import os
import json
import aio_pika
import asyncio
from datetime import datetime
from decimal import Decimal

RABBIT_URL = os.getenv("RABBIT_URL")
QUEUE_NAME = "transactions"


async def publish_event(payload: dict):
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()

    await channel.declare_queue(QUEUE_NAME, durable=True)

    message = aio_pika.Message(
        body=json.dumps(payload, default=str).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )

    await channel.default_exchange.publish(
        message,
        routing_key=QUEUE_NAME,
    )

    await connection.close()


def publish_transaction_event(
    *,
    event_type: str,
    transaction_id: int,
    account_id: int,
    account_number: str,
    account_name: str,
    amount: Decimal,
    counterparty_account_number: str | None = None,
    counterparty_name: str | None = None,
):
    payload = {
        "event_type": event_type,
        "transaction_id": transaction_id,
        "account_id": account_id,
        "account_number": account_number,
        "account_name": account_name,
        # "counterparty_account_number": counterparty_account_number,
        # "counterparty_name": counterparty_name,
        "amount": float(amount),
        "currency": "EUR",
        "timestamp": datetime.utcnow().isoformat(),
    }
    if counterparty_account_number:
        payload["counterparty_account_number"] = counterparty_account_number

    if counterparty_name:
        payload["counterparty_name"] = counterparty_name

    asyncio.run(publish_event(payload))
