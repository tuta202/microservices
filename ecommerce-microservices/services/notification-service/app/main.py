import asyncio, json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .messaging import connect, declare_consumer_queue
async def consume():
 conn=await connect(); ch=await conn.channel(); await ch.set_qos(prefetch_count=20)
 q=await declare_consumer_queue(ch,'notification.events.queue',['payment.succeeded','payment.failed','inventory.rejected'])
 async with q.iterator() as it:
  async for msg in it:
   async with msg.process(requeue=False):
    e=json.loads(msg.body); print({'notification_for':e['aggregate_id'],'event':e['event_type'],'correlation_id':e['correlation_id']})
@asynccontextmanager
async def lifespan(app):
 t=asyncio.create_task(consume()); yield; t.cancel()
app=FastAPI(title='notification-service',lifespan=lifespan)
@app.get('/health')
async def health():return {'status':'ok'}
