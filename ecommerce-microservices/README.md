# E-commerce Microservices Reference

Project học microservice theo luồng Order → Inventory → Payment → Notification.

## Stack
- Python 3.12, FastAPI
- RabbitMQ
- PostgreSQL database-per-service
- Transactional Outbox
- Inbox / idempotent consumer
- Manual ACK, retry queue, DLQ
- Choreography Saga
- Docker Compose

## Luồng nghiệp vụ
1. `POST /orders` tạo order `PENDING` và ghi `OrderCreated` vào outbox trong cùng transaction.
2. Outbox publisher gửi `OrderCreated` lên RabbitMQ.
3. Inventory Service reserve stock, phát `InventoryReserved` hoặc `InventoryRejected`.
4. Payment Service xử lý `InventoryReserved`, phát `PaymentSucceeded` hoặc `PaymentFailed`.
5. Order Service cập nhật `CONFIRMED` hoặc `CANCELLED`.
6. Nếu payment fail, Inventory Service nhận `PaymentFailed` và release stock.
7. Notification Service nhận các event cuối và ghi log mô phỏng gửi thông báo.

## Chạy project
```bash
cp .env.example .env
docker compose up --build
```

Tạo đơn:
```bash
curl -X POST http://localhost:8001/orders \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"c-001","amount":120000,"items":[{"product_id":"p-001","quantity":2}]}'
```

Xem order:
```bash
curl http://localhost:8001/orders/<ORDER_ID>
```

RabbitMQ UI: http://localhost:15672 (`guest` / `guest`)

## Cách học
Đọc theo thứ tự:
1. `docs/01-architecture.md`
2. `services/order-service/app/main.py`
3. `services/order-service/app/outbox.py`
4. `services/inventory-service/app/consumer.py`
5. `services/payment-service/app/consumer.py`
6. `docs/02-failure-labs.md`
7. `docs/03-interview-map.md`

## Phạm vi
Đây là reference project đủ để học và phỏng vấn. Một hệ thống production thực tế còn cần Kubernetes, secret manager, tracing backend, schema registry, autoscaling, CI/CD, backup/restore và security hardening.
