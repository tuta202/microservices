import os, asyncpg
pool: asyncpg.Pool | None = None
async def init_db():
    global pool
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    async with pool.acquire() as c:
        await c.execute('''
        CREATE TABLE IF NOT EXISTS orders(
          id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, amount BIGINT NOT NULL,
          items JSONB NOT NULL, status TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS outbox_events(
          event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, aggregate_id TEXT NOT NULL,
          payload JSONB NOT NULL, correlation_id TEXT NOT NULL, published_at TIMESTAMPTZ
        );
        CREATE TABLE IF NOT EXISTS inbox_events(
          event_id TEXT PRIMARY KEY, processed_at TIMESTAMPTZ DEFAULT now()
        );
        ''')
