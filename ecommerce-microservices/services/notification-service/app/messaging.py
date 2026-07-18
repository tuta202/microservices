import os
import aio_pika

RABBITMQ_URL = os.environ["RABBITMQ_URL"]
EXCHANGE = "ecommerce.events"
DLX = "ecommerce.dlx"

async def connect():
    return await aio_pika.connect_robust(RABBITMQ_URL)

async def declare_topology(channel: aio_pika.abc.AbstractChannel):
    exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
    dlx = await channel.declare_exchange(DLX, aio_pika.ExchangeType.DIRECT, durable=True)
    return exchange, dlx

async def declare_consumer_queue(channel, name: str, bindings: list[str]):
    exchange, dlx = await declare_topology(channel)
    queue = await channel.declare_queue(
        name,
        durable=True,
        arguments={"x-dead-letter-exchange": DLX, "x-dead-letter-routing-key": name + ".dead"},
    )
    for key in bindings:
        await queue.bind(exchange, key)
    dlq = await channel.declare_queue(name + ".dlq", durable=True)
    await dlq.bind(dlx, name + ".dead")
    return queue
