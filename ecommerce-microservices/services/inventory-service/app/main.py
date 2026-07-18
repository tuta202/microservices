import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from . import db
from .consumer import run_consumer
@asynccontextmanager
async def lifespan(app):
    await db.init_db(); t=asyncio.create_task(run_consumer()); yield; t.cancel()
app=FastAPI(title='inventory-service',lifespan=lifespan)
@app.get('/health')
async def health():return {'status':'ok'}
@app.get('/stock')
async def stock():
    async with db.pool.acquire() as c:return [dict(x) for x in await c.fetch('SELECT * FROM stock ORDER BY product_id')]
