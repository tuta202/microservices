import asyncio, json
from aio_pika import Message, DeliveryMode
from . import db
from .common import envelope
from .messaging import connect, declare_consumer_queue, declare_topology

async def publish_pending(ch):
    ex,_=await declare_topology(ch)
    async with db.pool.acquire() as c:
        rows=await c.fetch("SELECT * FROM outbox_events WHERE published_at IS NULL LIMIT 100")
        for r in rows:
            await ex.publish(Message(json.dumps(dict(r['payload'])).encode(),delivery_mode=DeliveryMode.PERSISTENT,message_id=r['event_id'],correlation_id=r['correlation_id']), routing_key=r['event_type'])
            await c.execute("UPDATE outbox_events SET published_at=now() WHERE event_id=$1",r['event_id'])

async def handle(event):
    t=event['event_type']; oid=event['aggregate_id']; corr=event['correlation_id']
    async with db.pool.acquire() as c:
      async with c.transaction():
        inserted=await c.fetchval("INSERT INTO inbox_events(event_id) VALUES($1) ON CONFLICT DO NOTHING RETURNING event_id",event['event_id'])
        if not inserted:return
        if t=='order.created':
            items=event['payload']['items']; ok=True
            for i in items:
                n=await c.fetchval("SELECT available FROM stock WHERE product_id=$1 FOR UPDATE",i['product_id'])
                if n is None or n < i['quantity']: ok=False; break
            if ok:
                for i in items: await c.execute("UPDATE stock SET available=available-$1 WHERE product_id=$2",i['quantity'],i['product_id'])
                await c.execute("INSERT INTO reservations(order_id,items,status) VALUES($1,$2::jsonb,'RESERVED') ON CONFLICT DO NOTHING",oid,json.dumps(items))
                out=envelope('inventory.reserved',oid,event['payload'],corr)
            else: out=envelope('inventory.rejected',oid,{"reason":"insufficient_stock"},corr)
        elif t=='payment.failed':
            row=await c.fetchrow("SELECT items,status FROM reservations WHERE order_id=$1 FOR UPDATE",oid)
            if not row or row['status']=='RELEASED': return
            for i in row['items']: await c.execute("UPDATE stock SET available=available+$1 WHERE product_id=$2",i['quantity'],i['product_id'])
            await c.execute("UPDATE reservations SET status='RELEASED' WHERE order_id=$1",oid)
            out=envelope('inventory.released',oid,{"reason":"payment_failed"},corr)
        else:return
        await c.execute("INSERT INTO outbox_events(event_id,event_type,aggregate_id,payload,correlation_id) VALUES($1,$2,$3,$4::jsonb,$5)",out['event_id'],out['event_type'],oid,json.dumps(out),corr)

async def run_consumer():
    conn=await connect(); ch=await conn.channel(publisher_confirms=True); await ch.set_qos(prefetch_count=10)
    q=await declare_consumer_queue(ch,'inventory.events.queue',['order.created','payment.failed'])
    while True:
      async with q.iterator() as it:
        async for msg in it:
          async with msg.process(requeue=False): await handle(json.loads(msg.body)); await publish_pending(ch)
