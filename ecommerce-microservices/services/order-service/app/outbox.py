import asyncio, json
from aio_pika import Message, DeliveryMode
from . import db
from .messaging import connect, declare_topology

async def run_outbox():
    conn = await connect()
    channel = await conn.channel(publisher_confirms=True)
    exchange, _ = await declare_topology(channel)
    while True:
        try:
            async with db.pool.acquire() as c:
                rows = await c.fetch('''SELECT event_id,event_type,aggregate_id,payload,correlation_id
                                      FROM outbox_events WHERE published_at IS NULL
                                      ORDER BY event_id LIMIT 100''')
                for r in rows:
                    body = dict(r["payload"])
                    msg = Message(json.dumps(body).encode(), delivery_mode=DeliveryMode.PERSISTENT,
                                  message_id=r["event_id"], correlation_id=r["correlation_id"])
                    await exchange.publish(msg, routing_key=r["event_type"])
                    await c.execute("UPDATE outbox_events SET published_at=now() WHERE event_id=$1", r["event_id"])
        except Exception as exc:
            print({"component":"outbox","status":"error","error":str(exc)})
        await asyncio.sleep(1)
