import os, asyncpg
pool=None
async def init_db():
 global pool; pool=await asyncpg.create_pool(os.environ['DATABASE_URL'])
 async with pool.acquire() as c:
  await c.execute('''CREATE TABLE IF NOT EXISTS payments(order_id TEXT PRIMARY KEY,amount BIGINT,status TEXT,provider_key TEXT UNIQUE);
  CREATE TABLE IF NOT EXISTS inbox_events(event_id TEXT PRIMARY KEY,processed_at TIMESTAMPTZ DEFAULT now());
  CREATE TABLE IF NOT EXISTS outbox_events(event_id TEXT PRIMARY KEY,event_type TEXT,aggregate_id TEXT,payload JSONB,correlation_id TEXT,published_at TIMESTAMPTZ);''')
