import json, os, random
from aio_pika import Message, DeliveryMode
from . import db
from .common import envelope
from .messaging import connect, declare_consumer_queue, declare_topology

async def run_consumer():
 conn=await connect(); ch=await conn.channel(publisher_confirms=True); await ch.set_qos(prefetch_count=5)
 q=await declare_consumer_queue(ch,'payment.events.queue',['inventory.reserved']); ex,_=await declare_topology(ch)
 async with q.iterator() as it:
  async for msg in it:
   async with msg.process(requeue=False):
    e=json.loads(msg.body); oid=e['aggregate_id']; corr=e['correlation_id']; amount=e['payload']['amount']; provider_key='pay-'+oid
    async with db.pool.acquire() as c:
     async with c.transaction():
      ins=await c.fetchval("INSERT INTO inbox_events(event_id) VALUES($1) ON CONFLICT DO NOTHING RETURNING event_id",e['event_id'])
      if not ins: continue
      failed=random.random() < float(os.getenv('PAYMENT_FAILURE_RATE','0.2'))
      status='FAILED' if failed else 'SUCCEEDED'
      await c.execute("INSERT INTO payments(order_id,amount,status,provider_key) VALUES($1,$2,$3,$4) ON CONFLICT(order_id) DO NOTHING",oid,amount,status,provider_key)
      out=envelope('payment.failed' if failed else 'payment.succeeded',oid,{"amount":amount,"provider_key":provider_key},corr)
      await c.execute("INSERT INTO outbox_events(event_id,event_type,aggregate_id,payload,correlation_id) VALUES($1,$2,$3,$4::jsonb,$5)",out['event_id'],out['event_type'],oid,json.dumps(out),corr)
    await ex.publish(Message(json.dumps(out).encode(),delivery_mode=DeliveryMode.PERSISTENT,message_id=out['event_id'],correlation_id=corr),routing_key=out['event_type'])
    async with db.pool.acquire() as c: await c.execute("UPDATE outbox_events SET published_at=now() WHERE event_id=$1",out['event_id'])
