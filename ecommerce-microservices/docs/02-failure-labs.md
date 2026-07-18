# 02 — Failure Labs

1. Tắt Inventory Service, tạo order, quan sát queue backlog; bật lại và kiểm tra xử lý tiếp.
2. Kill consumer sau DB commit nhưng trước ACK; kiểm tra message redelivery và inbox chống duplicate.
3. Đặt `PAYMENT_FAILURE_RATE=1.0`; kiểm tra compensation release inventory và cancel order.
4. Tắt RabbitMQ, tạo order; kiểm tra order + outbox vẫn commit. Bật lại RabbitMQ và kiểm tra outbox publisher gửi event.
5. Publish payload sai schema; kiểm tra message vào DLQ.
6. Chạy hai instance Inventory Service; kiểm tra competing consumers và unique constraint chống double reservation.
7. Làm outbox publisher crash sau publish trước mark published; kiểm tra consumer idempotency.
