# 03 — Interview Map

| Khái niệm | File nên đọc |
|---|---|
| Exchange, queue, routing | `app/messaging.py` |
| Manual ACK/NACK | `consumer.py` |
| Retry/DLQ | `messaging.py`, `consumer.py` |
| Outbox | `order-service/app/outbox.py` |
| Idempotency/Inbox | `inventory-service/app/consumer.py` |
| Saga | event handlers của ba service |
| Database per service | `docker-compose.yml` |
| Eventual consistency | status order và event flow |

Câu hỏi trọng tâm:
- DB commit rồi publish fail thì sao?
- Consumer commit rồi crash trước ACK thì sao?
- Vì sao vẫn có duplicate dù dùng outbox?
- Payment thành công nhưng event thất lạc thì phục hồi thế nào?
