import asyncio, json, uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from . import db
from .common import envelope
from .outbox import run_outbox
from .consumer import run_consumer

class Item(BaseModel): product_id: str; quantity: int
class CreateOrder(BaseModel): customer_id: str; amount: int; items: list[Item]

@asynccontextmanager
async def lifespan(app):
    await db.init_db()
    tasks=[asyncio.create_task(run_outbox()), asyncio.create_task(run_consumer())]
    yield
    for t in tasks: t.cancel()

app=FastAPI(title="order-service", lifespan=lifespan)

@app.get("/health")
async def health(): return {"status":"ok"}

@app.post("/orders", status_code=202)
async def create_order(req: CreateOrder):
    oid=str(uuid.uuid4()); corr=str(uuid.uuid4())
    event=envelope("order.created", oid, {"customer_id":req.customer_id,"amount":req.amount,"items":[i.model_dump() for i in req.items]}, corr)
    async with db.pool.acquire() as c:
        async with c.transaction():
            await c.execute("INSERT INTO orders(id,customer_id,amount,items,status) VALUES($1,$2,$3,$4::jsonb,'PENDING')", oid, req.customer_id, req.amount, json.dumps([i.model_dump() for i in req.items]))
            await c.execute("INSERT INTO outbox_events(event_id,event_type,aggregate_id,payload,correlation_id) VALUES($1,$2,$3,$4::jsonb,$5)", event["event_id"], event["event_type"], oid, json.dumps(event), corr)
    return {"order_id":oid,"status":"PENDING","correlation_id":corr}

@app.get("/orders/{order_id}")
async def get_order(order_id:str):
    async with db.pool.acquire() as c: row=await c.fetchrow("SELECT * FROM orders WHERE id=$1", order_id)
    if not row: raise HTTPException(404,"order not found")
    return dict(row)
