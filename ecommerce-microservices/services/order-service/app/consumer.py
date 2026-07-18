import json
from . import db
from .messaging import connect, declare_consumer_queue

QUEUE = "order.events.queue"
BINDINGS = ["inventory.rejected", "payment.succeeded", "payment.failed"]

async def run_consumer():
    conn = await connect(); ch = await conn.channel(); await ch.set_qos(prefetch_count=10)
    q = await declare_consumer_queue(ch, QUEUE, BINDINGS)
    async with q.iterator() as it:
        async for msg in it:
            async with msg.process(requeue=False):
                event = json.loads(msg.body)
                async with db.pool.acquire() as c:
                    async with c.transaction():
                        inserted = await c.fetchval('''INSERT INTO inbox_events(event_id) VALUES($1)
                            ON CONFLICT DO NOTHING RETURNING event_id''', event["event_id"])
                        if not inserted: continue
                        t = event["event_type"]
                        status = "CONFIRMED" if t == "payment.succeeded" else "CANCELLED"
                        await c.execute("UPDATE orders SET status=$1 WHERE id=$2", status, event["aggregate_id"])
