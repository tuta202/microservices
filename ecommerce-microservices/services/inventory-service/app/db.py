import os, asyncpg
pool=None
async def init_db():
    global pool
    pool=await asyncpg.create_pool(os.environ["DATABASE_URL"])
    async with pool.acquire() as c:
        await c.execute('''
        CREATE TABLE IF NOT EXISTS stock(product_id TEXT PRIMARY KEY, available INT NOT NULL);
        INSERT INTO stock(product_id,available) VALUES('p-001',100),('p-002',50) ON CONFLICT DO NOTHING;
        CREATE TABLE IF NOT EXISTS reservations(order_id TEXT PRIMARY KEY, items JSONB NOT NULL, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inbox_events(event_id TEXT PRIMARY KEY, processed_at TIMESTAMPTZ DEFAULT now());
        CREATE TABLE IF NOT EXISTS outbox_events(event_id TEXT PRIMARY KEY,event_type TEXT,aggregate_id TEXT,payload JSONB,correlation_id TEXT,published_at TIMESTAMPTZ);
        ''')
