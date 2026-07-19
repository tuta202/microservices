# Tuần 4: Scaling Và Stateful Workloads

## Mục Tiêu Tuần Này

Sau tuần 4, bạn cần hiểu cách Kubernetes scale workload và cách xử lý các workload có state như database, message broker, batch job.

Deliverable cuối tuần:

- cấu hình được `HorizontalPodAutoscaler` cho stateless service
- hiểu HPA cần metrics server và resource requests
- tạo được `Job` và `CronJob`
- hiểu `Volume`, `PersistentVolume`, `PersistentVolumeClaim`, `StorageClass`
- hiểu `StatefulSet` khác `Deployment` ở đâu
- deploy được PostgreSQL/RabbitMQ trong lab để học storage và identity
- phân biệt rõ: chạy stateful workload trong lab khác với production

## Mental Model Tổng Quan

Stateless service tương đối dễ scale:

```text
Order Service replicas: 2 -> 10
```

Vì mỗi Pod gần như giống nhau, không cần identity cố định, không giữ dữ liệu lâu dài trong filesystem.

Stateful workload khó hơn:

```text
PostgreSQL
RabbitMQ cluster
Kafka
Redis cluster
```

Vì chúng cần:

- dữ liệu tồn tại sau khi Pod bị xóa
- identity ổn định
- thứ tự khởi động/tắt trong một số trường hợp
- backup/restore
- replication
- upgrade cẩn thận
- hiểu rõ consistency và failure mode

Điểm quan trọng:

```text
Kubernetes có thể chạy stateful workload, nhưng không tự biến database thành managed database.
```

Trong production, thường ưu tiên managed database/message broker hoặc Operator đáng tin cậy.

## Ngày 16: Horizontal Pod Autoscaler

### HPA là gì?

`HorizontalPodAutoscaler` tự động tăng/giảm số Pod replica dựa trên metric.

Phổ biến nhất:

- CPU utilization
- memory utilization
- custom metrics như request rate, queue depth

Ví dụ:

```text
CPU trung bình > 70%
  -> tăng replicas
CPU giảm ổn định
  -> giảm replicas
```

### Điều kiện để HPA hoạt động

HPA cần:

- metrics server hoặc metrics pipeline tương ứng
- Deployment/ReplicaSet target
- `resources.requests.cpu` nếu scale theo CPU utilization

Nếu Pod không khai báo CPU request, HPA khó tính phần trăm CPU utilization.

### Manifest Deployment có requests

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      containers:
        - name: order-service
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

Apply:

```bash
kubectl apply -f order-deployment.yaml
```

### Tạo HPA bằng lệnh

```bash
kubectl autoscale deployment order-service --cpu-percent=70 --min=2 --max=10
```

Kiểm tra:

```bash
kubectl get hpa
kubectl describe hpa order-service
kubectl get pods
```

### Tạo HPA bằng YAML

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Load test trong lab

Tạo Pod tạo tải:

```bash
kubectl run load-generator --rm -it --image=busybox:1.36 -- sh
```

Trong Pod:

```sh
while true; do wget -q -O- http://order-service; done
```

Quan sát:

```bash
kubectl get hpa -w
kubectl get pods -w
```

Lưu ý: `nginx` có thể không tạo đủ CPU load để HPA scale rõ ràng. Với app thật, bạn nên dùng endpoint tiêu tốn CPU có kiểm soát, hoặc dùng tool load test phù hợp.

### HPA không giải quyết mọi bottleneck

Scale app không đồng nghĩa hệ thống nhanh hơn.

Ví dụ:

```text
Order Service scale lên 20 Pod
PostgreSQL chỉ chịu được 100 connections
Mỗi Pod mở 20 connections
Tổng connections = 400
Database quá tải
```

Kết quả: scale app có thể làm hệ thống tệ hơn.

Khi scale backend service, cần nhìn cả:

- database connection pool
- RabbitMQ queue depth
- consumer concurrency
- downstream rate limit
- external API quota
- cache hit rate

### Câu hỏi tự kiểm tra

- HPA scale dựa trên metric nào?
- Vì sao CPU request ảnh hưởng HPA?
- Metrics server dùng để làm gì?
- Vì sao stateless service dễ scale hơn stateful service?
- Khi scale app làm DB quá tải, bạn sẽ kiểm tra gì?

## Ngày 17: Job Và CronJob

### Job là gì?

`Job` dùng cho workload chạy đến khi hoàn thành.

Ví dụ:

- data migration một lần
- import dữ liệu
- reconciliation task
- kiểm tra DLQ thủ công
- cleanup dữ liệu tạm

Khác `Deployment`:

```text
Deployment: chạy liên tục
Job: chạy xong thì kết thúc
```

### Job manifest

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: outbox-cleanup
spec:
  backoffLimit: 3
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: outbox-cleanup
          image: busybox:1.36
          command: ["sh", "-c", "echo cleaning outbox; sleep 5; echo done"]
```

Apply:

```bash
kubectl apply -f outbox-cleanup-job.yaml
```

Kiểm tra:

```bash
kubectl get jobs
kubectl get pods
kubectl logs job/outbox-cleanup
kubectl describe job outbox-cleanup
```

### CronJob là gì?

`CronJob` tạo Job theo lịch.

Ví dụ trong ecommerce/microservices:

- mỗi 5 phút tìm saga bị treo
- cleanup expired inventory reservation
- inspect DLQ
- reconcile payment status
- xóa outbox event đã publish thành công sau N ngày

### CronJob manifest

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: saga-reconciliation
spec:
  schedule: "*/5 * * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: saga-reconciliation
              image: busybox:1.36
              command: ["sh", "-c", "echo checking stuck sagas; date"]
```

Apply:

```bash
kubectl apply -f saga-reconciliation-cronjob.yaml
```

Kiểm tra:

```bash
kubectl get cronjobs
kubectl get jobs
kubectl logs job/<job-name>
```

### Cấu hình quan trọng

| Field | Ý nghĩa |
| --- | --- |
| `schedule` | Lịch chạy theo cron format. |
| `concurrencyPolicy` | Có cho phép job mới chạy khi job cũ chưa xong không. |
| `backoffLimit` | Số lần retry khi Job fail. |
| `successfulJobsHistoryLimit` | Giữ lại bao nhiêu Job thành công. |
| `failedJobsHistoryLimit` | Giữ lại bao nhiêu Job thất bại. |

Với reconciliation job, `concurrencyPolicy: Forbid` thường an toàn hơn để tránh hai job xử lý cùng một dữ liệu.

### Câu hỏi tự kiểm tra

- Job khác Deployment ở điểm nào?
- CronJob tạo resource gì khi đến lịch?
- Khi nào dùng `concurrencyPolicy: Forbid`?
- Vì sao reconciliation job quan trọng trong hệ thống event-driven?

## Ngày 18: Volume, PV Và PVC

### Filesystem của container là ephemeral

Nếu container ghi dữ liệu vào filesystem bên trong container, dữ liệu đó có thể mất khi:

- container restart
- Pod bị xóa
- Pod được tạo lại trên Node khác

Với stateless service, điều này bình thường.

Với database, message broker, file storage, điều này nguy hiểm.

### Volume là gì?

`Volume` gắn storage vào Pod.

Một số loại volume:

- `emptyDir`: tồn tại theo vòng đời Pod, mất khi Pod bị xóa
- `configMap`: mount ConfigMap thành file
- `secret`: mount Secret thành file
- persistent volume qua PVC

### PV, PVC, StorageClass

Ba khái niệm chính:

| Khái niệm | Vai trò |
| --- | --- |
| PersistentVolume | Storage thật được Kubernetes biết tới. |
| PersistentVolumeClaim | Yêu cầu xin storage từ workload. |
| StorageClass | Cách provision storage động. |

Mental model:

```text
Pod -> PVC -> StorageClass -> PV -> storage thật
```

Map từ Docker Compose:

```yaml
volumes:
  postgres-data:
```

sang Kubernetes:

```text
PersistentVolumeClaim
  -> PersistentVolume
  -> StorageClass
```

### PVC manifest

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

Apply:

```bash
kubectl apply -f postgres-pvc.yaml
```

Kiểm tra:

```bash
kubectl get pvc
kubectl describe pvc postgres-data
kubectl get storageclass
```

### Mount PVC vào Pod

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres-lab
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres-lab
  template:
    metadata:
      labels:
        app: postgres-lab
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          env:
            - name: POSTGRES_PASSWORD
              value: postgres
          ports:
            - containerPort: 5432
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: postgres-data
```

Ghi chú: ví dụ này dùng để học. Production PostgreSQL nên dùng managed database hoặc operator có backup/HA rõ ràng.

### Access modes

| Access mode | Ý nghĩa đơn giản |
| --- | --- |
| ReadWriteOnce | Một Node mount read-write. Phổ biến cho disk database. |
| ReadOnlyMany | Nhiều Node mount read-only. |
| ReadWriteMany | Nhiều Node mount read-write, cần storage hỗ trợ. |
| ReadWriteOncePod | Một Pod duy nhất mount read-write. |

Không phải storage class nào cũng hỗ trợ mọi access mode.

### Câu hỏi tự kiểm tra

- Vì sao container filesystem không phù hợp để lưu database?
- PVC khác PV ở điểm nào?
- StorageClass dùng để làm gì?
- `ReadWriteOnce` có nghĩa là gì?

## Ngày 19: StatefulSet

### StatefulSet là gì?

`StatefulSet` dùng cho workload cần identity ổn định.

Khác với Deployment, StatefulSet cung cấp:

- Pod name ổn định: `postgres-0`, `postgres-1`
- network identity ổn định
- thứ tự tạo/xóa Pod có kiểm soát
- persistent storage riêng cho từng replica
- thường dùng với Headless Service

Deployment phù hợp cho stateless app:

```text
order-service-abc123
order-service-def456
```

Pod nào cũng tương đương nhau.

StatefulSet phù hợp khi identity quan trọng:

```text
rabbitmq-0
rabbitmq-1
rabbitmq-2
```

### Headless Service là gì?

Headless Service dùng:

```yaml
clusterIP: None
```

Nó cho phép DNS trỏ đến từng Pod cụ thể trong StatefulSet.

Ví dụ:

```text
rabbitmq-0.rabbitmq.ecommerce.svc.cluster.local
rabbitmq-1.rabbitmq.ecommerce.svc.cluster.local
```

### StatefulSet manifest đơn giản

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  clusterIP: None
  selector:
    app: postgres
  ports:
    - name: postgres
      port: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          env:
            - name: POSTGRES_PASSWORD
              value: postgres
          ports:
            - containerPort: 5432
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes:
          - ReadWriteOnce
        resources:
          requests:
            storage: 1Gi
```

Apply:

```bash
kubectl apply -f postgres-statefulset.yaml
```

Kiểm tra:

```bash
kubectl get statefulsets
kubectl get pods
kubectl get pvc
kubectl get service postgres
```

### Production reality

StatefulSet là công cụ hạ tầng, không phải giải pháp database production hoàn chỉnh.

Production database cần thêm:

- backup/restore
- replication
- failover
- monitoring
- point-in-time recovery
- upgrade plan
- disaster recovery
- security hardening

Vì vậy production thường ưu tiên:

- managed database
- managed message broker
- Kubernetes Operator trưởng thành

Đây là câu trả lời phỏng vấn tốt:

```text
Tôi hiểu StatefulSet dùng để chạy workload cần identity và storage ổn định. Nhưng với production database, tôi ưu tiên managed service hoặc operator có backup, HA, restore và upgrade strategy rõ ràng.
```

### Câu hỏi tự kiểm tra

- StatefulSet khác Deployment ở điểm nào?
- Vì sao StatefulSet cần stable identity?
- Headless Service dùng để làm gì?
- Vì sao không nên tự deploy database production chỉ vì biết StatefulSet?

## Ngày 20: PostgreSQL Và RabbitMQ Trong Lab

### Lab vs Production

Trong local learning project, chạy PostgreSQL và RabbitMQ trong cluster là rất tốt để học:

- PVC
- StatefulSet
- Service DNS
- Pod restart
- app reconnect

Nhưng trong production:

```text
Lab: chạy PostgreSQL/RabbitMQ trong cluster để học.
Production: ưu tiên managed services hoặc operator có backup/HA rõ ràng.
```

### PostgreSQL lab

Tạo PostgreSQL bằng StatefulSet như phần ngày 19.

Tạo Service thường để app gọi:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  selector:
    app: postgres
  ports:
    - name: postgres
      port: 5432
      targetPort: 5432
```

App gọi:

```text
postgres:5432
```

### RabbitMQ lab

Ví dụ RabbitMQ đơn giản:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: rabbitmq
spec:
  serviceName: rabbitmq
  replicas: 1
  selector:
    matchLabels:
      app: rabbitmq
  template:
    metadata:
      labels:
        app: rabbitmq
    spec:
      containers:
        - name: rabbitmq
          image: rabbitmq:3.13-management-alpine
          ports:
            - containerPort: 5672
            - containerPort: 15672
          volumeMounts:
            - name: data
              mountPath: /var/lib/rabbitmq
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes:
          - ReadWriteOnce
        resources:
          requests:
            storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq
spec:
  selector:
    app: rabbitmq
  ports:
    - name: amqp
      port: 5672
      targetPort: 5672
    - name: management
      port: 15672
      targetPort: 15672
```

Apply:

```bash
kubectl apply -f rabbitmq-lab.yaml
```

Kiểm tra:

```bash
kubectl get statefulsets
kubectl get pods
kubectl get pvc
kubectl get service rabbitmq
```

Port-forward RabbitMQ management UI:

```bash
kubectl port-forward service/rabbitmq 15672:15672
```

Mở:

```text
http://localhost:15672
```

Với image mặc định, user/password thường là `guest`/`guest` trong lab local.

### Failure Lab

Xóa RabbitMQ Pod:

```bash
kubectl delete pod rabbitmq-0
kubectl get pods -w
kubectl get pvc
```

Xóa PostgreSQL Pod:

```bash
kubectl delete pod postgres-0
kubectl get pods -w
kubectl get pvc
```

Cần quan sát:

- Pod được tạo lại
- PVC vẫn còn
- dữ liệu có cơ hội tồn tại vì gắn với PVC
- app cần reconnect được khi broker/database restart

Kiểm tra PVC:

```bash
kubectl get pvc
kubectl describe pvc <pvc-name>
```

### Câu hỏi tự kiểm tra

- Khi xóa Pod của StatefulSet, PVC có bị xóa không?
- App cần xử lý gì khi RabbitMQ/PostgreSQL restart?
- Vì sao local lab có thể chạy DB trong cluster, còn production nên thận trọng hơn?

## Bài Thực Hành Tổng Hợp Cuối Tuần

Mục tiêu:

```text
order-service
  -> HPA min=2 max=10
  -> gọi postgres qua Service DNS
  -> gọi rabbitmq qua Service DNS

postgres
  -> StatefulSet
  -> PVC

rabbitmq
  -> StatefulSet
  -> PVC

maintenance jobs
  -> Job / CronJob
```

Thực hiện:

```bash
kubectl apply -f order-deployment.yaml
kubectl autoscale deployment order-service --cpu-percent=70 --min=2 --max=10
kubectl apply -f postgres-statefulset.yaml
kubectl apply -f rabbitmq-lab.yaml
kubectl apply -f saga-reconciliation-cronjob.yaml
```

Kiểm tra:

```bash
kubectl get deployments
kubectl get hpa
kubectl get statefulsets
kubectl get pods
kubectl get pvc
kubectl get jobs
kubectl get cronjobs
```

Phá và debug:

```text
Tạo load để quan sát HPA
Xóa rabbitmq-0
Xóa postgres-0
Quan sát PVC
Kiểm tra app reconnect
Chạy CronJob thủ công nếu cần
```

Chạy CronJob thủ công:

```bash
kubectl create job --from=cronjob/saga-reconciliation saga-reconciliation-manual
kubectl logs job/saga-reconciliation-manual
```

## Cheatsheet Tuần 4

### HPA

```bash
kubectl autoscale deployment order-service --cpu-percent=70 --min=2 --max=10
kubectl get hpa
kubectl describe hpa order-service
kubectl top pods
kubectl top nodes
```

### Job và CronJob

```bash
kubectl get jobs
kubectl describe job <job-name>
kubectl logs job/<job-name>
kubectl get cronjobs
kubectl describe cronjob <cronjob-name>
kubectl create job --from=cronjob/<cronjob-name> <manual-job-name>
```

### Storage

```bash
kubectl get storageclass
kubectl get pv
kubectl get pvc
kubectl describe pvc <pvc-name>
```

### StatefulSet

```bash
kubectl get statefulsets
kubectl describe statefulset <name>
kubectl get pods
kubectl get pods -o wide
kubectl delete pod <stateful-pod-name>
```

## Những Lỗi Hay Gặp

### HPA không hiện CPU metric

Nguyên nhân thường gặp:

- chưa cài metrics server
- Pod không có CPU request
- metrics server chưa scrape được Node/Pod

Debug:

```bash
kubectl top pods
kubectl describe hpa order-service
```

### Scale app làm dependency quá tải

Scale Pod mà không kiểm soát DB connection pool, RabbitMQ consumer concurrency hoặc external API rate limit có thể làm hệ thống chậm hơn.

### PVC Pending

Nguyên nhân thường gặp:

- cluster không có StorageClass mặc định
- access mode không được storage hỗ trợ
- storage provisioner lỗi

Debug:

```bash
kubectl get storageclass
kubectl describe pvc <pvc-name>
```

### CronJob chạy chồng nhau

Nếu job cũ chưa xong mà job mới bắt đầu, dữ liệu có thể bị xử lý trùng.

Cân nhắc:

```yaml
concurrencyPolicy: Forbid
```

## Checklist Kết Thúc Tuần

Bạn đã hoàn thành tuần 4 nếu có thể tự trả lời:

- HPA cần điều kiện gì để hoạt động?
- Vì sao CPU request quan trọng với HPA?
- HPA không giải quyết được những bottleneck nào?
- Job khác CronJob ở điểm nào?
- Reconciliation job dùng để làm gì?
- Container filesystem ephemeral nghĩa là gì?
- PVC, PV, StorageClass liên hệ với nhau thế nào?
- StatefulSet khác Deployment ở điểm nào?
- Headless Service dùng để làm gì?
- Vì sao production database nên dùng managed service hoặc operator?

Bạn cũng cần tự làm được:

```text
Tạo HPA cho order-service
Quan sát scale up/scale down
Tạo Job chạy một lần
Tạo CronJob chạy theo lịch
Tạo PVC
Mount PVC cho workload
Deploy PostgreSQL/RabbitMQ lab bằng StatefulSet
Xóa Pod stateful và kiểm tra PVC vẫn còn
```

## Đáp Án Gợi Ý Cho Câu Hỏi Tự Kiểm Tra

### Ngày 16

- HPA scale dựa trên metrics như CPU, memory hoặc custom metrics. Ví dụ phổ biến nhất là CPU utilization trung bình.
- CPU request quan trọng vì HPA tính CPU utilization theo tỷ lệ giữa CPU đang dùng và CPU request.
- Metrics server cung cấp resource metrics như CPU/memory cho Pod và Node để HPA và `kubectl top` sử dụng.
- Stateless service dễ scale hơn vì mỗi replica gần như giống nhau, không cần identity cố định và không giữ dữ liệu local quan trọng.
- Khi scale app làm DB quá tải, cần kiểm tra connection pool, số connection tổng, query latency, database CPU/memory/IO, queue depth, retry rate và downstream rate limit.

### Ngày 17

- Job chạy đến khi hoàn thành rồi dừng. Deployment chạy lâu dài và luôn cố giữ số replica mong muốn.
- CronJob tạo Job theo lịch cron.
- Dùng `concurrencyPolicy: Forbid` khi không muốn job mới chạy chồng lên job cũ, đặc biệt với cleanup/reconciliation dễ xử lý trùng dữ liệu.
- Reconciliation job quan trọng trong hệ thống event-driven vì nó phát hiện và sửa các trạng thái bị kẹt, event thất lạc, saga chưa hoàn tất hoặc outbox backlog.

### Ngày 18

- Container filesystem không phù hợp để lưu database vì dữ liệu có thể mất khi container/Pod bị xóa hoặc tạo lại.
- PVC là yêu cầu xin storage từ workload. PV là storage thật được Kubernetes bind cho PVC.
- StorageClass định nghĩa cách provision storage, ví dụ loại disk, provisioner và policy.
- `ReadWriteOnce` nghĩa là volume có thể được mount read-write bởi một Node tại một thời điểm.

### Ngày 19

- StatefulSet khác Deployment ở stable Pod identity, stable network identity, ordered deployment/termination và storage riêng cho từng replica.
- StatefulSet cần stable identity vì nhiều hệ thống stateful cần biết node nào là node nào, ví dụ database replica hoặc broker node.
- Headless Service cung cấp DNS trực tiếp cho từng Pod của StatefulSet thay vì một virtual IP load-balanced thông thường.
- Không nên tự deploy database production chỉ vì biết StatefulSet vì production cần backup, restore, HA, failover, monitoring, security và upgrade strategy nghiêm túc.

### Ngày 20

- Khi xóa Pod của StatefulSet, PVC thường không bị xóa. Pod mới có thể mount lại PVC cũ.
- App cần retry/reconnect khi RabbitMQ/PostgreSQL restart, đồng thời xử lý timeout, backoff và idempotency để tránh lỗi dây chuyền.
- Local lab chạy DB trong cluster giúp học storage và lifecycle. Production nên thận trọng vì database/broker cần vận hành chuyên sâu, backup/HA/restore rõ ràng.
