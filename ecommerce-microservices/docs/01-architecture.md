# 01 — Architecture

## Service boundaries
- Order Service sở hữu vòng đời order.
- Inventory Service sở hữu tồn kho và reservation.
- Payment Service sở hữu payment attempt và trạng thái thanh toán.
- Notification Service chỉ phản ứng với domain event cuối.

Không service nào đọc database của service khác.

## Event flow
```text
OrderCreated
  -> InventoryReserved | InventoryRejected
InventoryReserved
  -> PaymentSucceeded | PaymentFailed
PaymentSucceeded
  -> OrderConfirmed
PaymentFailed
  -> OrderCancelled + InventoryReleased
```

## Reliability
- Producer: transactional outbox.
- Consumer: inbox table + unique event id.
- Broker: durable exchange/queue, persistent message, publisher confirms.
- Delivery model: at-least-once.
- Retry: retry queue có TTL và dead-letter về main queue.
- Poison message: dead-letter queue.

## Saga
Project dùng choreography saga để dễ quan sát event flow. Với workflow dài hoặc nhiều nhánh, nên chuyển sang orchestrator/state machine.
