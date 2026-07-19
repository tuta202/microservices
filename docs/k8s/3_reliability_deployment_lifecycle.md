# Tuần 3: Reliability Và Deployment Lifecycle

## Mục Tiêu Tuần Này

Tuần 3 là một trong những tuần quan trọng nhất với Backend Engineer, vì đây là phần biến một service “chạy được” thành một service “vận hành được”.

Sau tuần này, mỗi service quan trọng nên có:

- readiness probe
- liveness probe
- startup probe nếu app khởi động chậm
- resource requests và limits
- rolling update rõ ràng
- rollback khi deploy lỗi
- graceful shutdown

Deliverable cuối tuần:

```text
Order Service
  -> readinessProbe
  -> livenessProbe
  -> startupProbe nếu cần
  -> resources.requests
  -> resources.limits
  -> rolling update strategy
  -> graceful termination
```

## Mental Model Tổng Quan

Ở tuần 1 và tuần 2, bạn đã học cách chạy service và route traffic.

Tuần 3 trả lời các câu hỏi production hơn:

```text
Pod đã sẵn sàng nhận traffic chưa?
Pod còn sống thật không, hay process đã treo?
App khởi động chậm thì Kubernetes có restart nhầm không?
Pod được cấp bao nhiêu CPU và memory?
Deploy version mới mà lỗi thì rollback thế nào?
Khi Pod bị terminate, request/message đang xử lý có bị mất không?
```

Kubernetes không tự biết app của bạn khỏe hay không. Bạn phải dạy Kubernetes bằng probes và cấu hình lifecycle.

## Ngày 11: Readiness Probe

### Readiness trả lời câu hỏi gì?

`readinessProbe` trả lời:

```text
Pod đã sẵn sàng nhận traffic chưa?
```

Nếu readiness fail:

- container vẫn chạy
- Pod vẫn tồn tại
- nhưng Pod bị loại khỏi Service endpoints
- traffic mới không được route tới Pod đó

Đây là cơ chế cực kỳ quan trọng để tránh gửi request vào app chưa sẵn sàng.

### Khi nào readiness nên fail?

Readiness nên fail khi app chưa thể xử lý request đúng cách.

Ví dụ:

- app chưa load xong config
- migration cần thiết chưa xong
- dependency bắt buộc để xử lý request chưa sẵn sàng
- app đang drain trong quá trình shutdown

Với backend service, endpoint readiness thường là:

```text
/health/ready
```

### Không nên readiness giả tạo

Không nên viết endpoint `/health/ready` luôn trả 200 chỉ vì process còn chạy.

Nếu app còn sống nhưng chưa xử lý request được, readiness phải fail.

Ví dụ:

```text
Order Service nhận request tạo order
Nhưng chưa kết nối được database bắt buộc
Readiness nên fail để Service chưa route traffic vào Pod này
```

### Manifest ví dụ

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
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
          image: ecommerce/order-service:v1
          ports:
            - containerPort: 8000
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 3
```

Ý nghĩa:

- `initialDelaySeconds`: chờ trước khi check lần đầu
- `periodSeconds`: khoảng cách giữa các lần check
- `timeoutSeconds`: mỗi lần check được phép chờ bao lâu
- `failureThreshold`: fail bao nhiêu lần liên tiếp thì xem là not ready

### Thực hành

Apply Deployment có readiness:

```bash
kubectl apply -f order-deployment.yaml
kubectl rollout status deployment/order-service
```

Kiểm tra Pod:

```bash
kubectl get pods
kubectl describe pod <pod-name>
```

Kiểm tra endpoints:

```bash
kubectl get endpoints order-service
```

Nếu readiness fail, Pod sẽ không nằm trong endpoints của Service.

### Failure Lab: làm readiness fail

Đổi path readiness sang path sai:

```yaml
readinessProbe:
  httpGet:
    path: /wrong-ready
    port: 8000
```

Apply lại:

```bash
kubectl apply -f order-deployment.yaml
kubectl get pods
kubectl get endpoints order-service
kubectl describe pod <pod-name>
```

Bạn cần quan sát:

- Pod có thể vẫn `Running`
- READY có thể là `0/1`
- Service endpoints không chứa Pod đó

### Câu hỏi tự kiểm tra

- Readiness khác trạng thái container running như thế nào?
- Nếu readiness fail, Pod có bị restart không?
- Vì sao readiness ảnh hưởng đến Service endpoints?
- Health endpoint readiness nên kiểm tra gì?

## Ngày 12: Liveness Và Startup Probe

### Liveness trả lời câu hỏi gì?

`livenessProbe` trả lời:

```text
Process có bị kẹt đến mức cần restart không?
```

Nếu liveness fail đủ số lần:

- Kubernetes restart container
- Pod có thể giữ nguyên tên
- restart count tăng

Liveness không dùng để quyết định route traffic. Việc đó là nhiệm vụ của readiness.

### Sai lầm phổ biến: liveness check database

Không nên để liveness phụ thuộc vào database hoặc RabbitMQ.

Ví dụ sai:

```text
Database tạm thời down
Liveness fail
Kubernetes restart toàn bộ app
Nhiều Pod cùng restart
Hệ thống càng tệ hơn
```

Hiện tượng này thường gọi là restart storm.

Liveness nên kiểm tra:

- process còn phản hồi không
- event loop/thread chính có bị treo không
- app có còn khả năng tự phục hồi không

Readiness mới nên kiểm tra dependency cần thiết để nhận traffic.

### Startup probe dùng khi nào?

`startupProbe` dùng cho app khởi động chậm.

Khi startup probe được cấu hình, Kubernetes chờ startup probe pass trước khi áp dụng liveness và readiness bình thường.

Dùng startup probe khi:

- app cần warm up cache
- app load model lớn
- app chạy migration nhẹ khi start
- JVM/.NET app khởi động lâu
- service cần nhiều thời gian để kết nối dependency

### Manifest ví dụ

```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 2
  failureThreshold: 3
startupProbe:
  httpGet:
    path: /health/startup
    port: 8000
  periodSeconds: 5
  failureThreshold: 30
```

Với cấu hình trên, app có tối đa khoảng:

```text
5 giây * 30 = 150 giây
```

để khởi động trước khi bị xem là startup fail.

### Phân biệt 3 loại probe

| Probe | Câu hỏi | Nếu fail thì sao? |
| --- | --- | --- |
| Readiness | Pod nhận traffic được chưa? | Pod bị loại khỏi Service endpoints. |
| Liveness | Container có cần restart không? | Container bị restart. |
| Startup | App đã khởi động xong chưa? | Trong lúc chưa pass, liveness/readiness chưa gây restart sớm. |

### Failure Lab

Làm readiness fail:

```text
Đổi path /health/ready thành path sai
Quan sát Pod bị remove khỏi endpoints
```

Làm liveness fail:

```text
Đổi path /health/live thành path sai
Quan sát restart count tăng
```

Lệnh quan sát:

```bash
kubectl get pods -w
kubectl describe pod <pod-name>
kubectl get endpoints order-service
```

### Câu hỏi tự kiểm tra

- Khi nào dùng readiness?
- Khi nào dùng liveness?
- Khi nào cần startup probe?
- Vì sao liveness không nên check database?

## Ngày 13: Resource Requests Và Limits

### Vì sao cần requests và limits?

Nếu bạn không khai báo resource, Kubernetes khó schedule workload một cách hợp lý.

`resources.requests` là lượng tài nguyên container cần để chạy ổn định.

`resources.limits` là mức tối đa container được phép sử dụng.

Ví dụ:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### CPU request và memory request

Scheduler dùng request để chọn Node.

Ví dụ Pod request:

```text
cpu: 500m
memory: 512Mi
```

Kubernetes sẽ tìm Node còn đủ tài nguyên allocatable để đặt Pod.

CPU đơn vị:

```text
1000m = 1 CPU core
100m = 0.1 CPU core
```

Memory đơn vị:

```text
128Mi
512Mi
1Gi
```

### CPU limit và memory limit

CPU limit:

- container bị throttle nếu dùng quá CPU limit
- thường làm app chậm hơn, không bị kill ngay

Memory limit:

- container có thể bị kill nếu dùng quá memory limit
- trạng thái thường thấy là `OOMKilled`

### QoS class

Kubernetes phân Pod vào QoS class dựa trên requests và limits:

| QoS | Điều kiện đơn giản |
| --- | --- |
| Guaranteed | Mỗi container có CPU/memory request bằng limit. |
| Burstable | Có request hoặc limit, nhưng không đủ điều kiện Guaranteed. |
| BestEffort | Không khai báo request/limit. |

Khi Node thiếu tài nguyên, Pod `BestEffort` dễ bị evict hơn.

### Manifest ví dụ

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
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
          image: ecommerce/order-service:v1
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

### Thực hành

Apply:

```bash
kubectl apply -f order-deployment.yaml
```

Kiểm tra:

```bash
kubectl describe pod <pod-name>
kubectl top pods
kubectl top nodes
```

Lưu ý: `kubectl top` cần metrics server. Nếu local cluster chưa có metrics server, lệnh có thể chưa chạy được.

### Failure Lab: memory limit quá thấp

Đặt memory limit rất thấp, ví dụ:

```yaml
resources:
  requests:
    memory: 16Mi
  limits:
    memory: 16Mi
```

Nếu app dùng quá mức này, container có thể bị `OOMKilled`.

Debug:

```bash
kubectl get pods
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

Tìm các dấu hiệu:

```text
Reason: OOMKilled
Exit Code: 137
```

### Câu hỏi tự kiểm tra

- Scheduler dùng request hay limit để chọn Node?
- CPU limit khác memory limit ở điểm nào?
- Vì sao memory limit quá thấp có thể gây OOMKilled?
- QoS class ảnh hưởng gì khi Node thiếu tài nguyên?

## Ngày 14: Rolling Update Và Rollback

### Rolling update là gì?

Rolling update cho phép deploy version mới từng phần, thay vì tắt toàn bộ version cũ rồi bật version mới.

Flow đơn giản:

```text
Tạo Pod version mới
Chờ Pod mới ready
Giảm Pod version cũ
Lặp lại cho đến khi toàn bộ workload chạy version mới
```

Nhờ readiness probe, Kubernetes biết khi nào Pod mới đủ sẵn sàng để nhận traffic.

### Deployment revision

Mỗi lần bạn thay đổi Pod template trong Deployment, Kubernetes tạo revision mới.

Ví dụ thay đổi:

- image tag
- env
- probe
- resource
- label trong Pod template

Không phải mọi thay đổi đều tạo revision. Thay đổi `replicas` thường không tạo revision mới.

### maxUnavailable và maxSurge

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1
    maxSurge: 1
```

Ý nghĩa:

- `maxUnavailable`: tối đa bao nhiêu Pod có thể unavailable trong lúc update
- `maxSurge`: tối đa bao nhiêu Pod được tạo thêm vượt quá số replicas mong muốn

Ví dụ `replicas: 3`, `maxUnavailable: 1`, `maxSurge: 1`:

```text
Trong rollout có thể có tối đa 4 Pod tạm thời
Và tối thiểu 2 Pod available
```

### Luôn dùng image version rõ ràng

Không nên dùng `latest` trong production.

Nên dùng:

```text
ecommerce/order-service:v1.2.3
ecommerce/order-service:2026-07-19-commitabc
```

Vì rollback và audit sẽ rõ ràng hơn.

### Thực hành rolling update

Đổi image:

```bash
kubectl set image deployment/order-service order-service=ecommerce/order-service:v2
```

Theo dõi:

```bash
kubectl rollout status deployment/order-service
kubectl get pods -w
```

Xem lịch sử:

```bash
kubectl rollout history deployment/order-service
```

Xem chi tiết revision:

```bash
kubectl rollout history deployment/order-service --revision=2
```

Rollback:

```bash
kubectl rollout undo deployment/order-service
```

Rollback về revision cụ thể:

```bash
kubectl rollout undo deployment/order-service --to-revision=1
```

### Failure Lab: deploy image lỗi

Deploy image không tồn tại:

```bash
kubectl set image deployment/order-service order-service=ecommerce/order-service:not-found
```

Quan sát:

```bash
kubectl rollout status deployment/order-service
kubectl get pods
kubectl describe pod <pod-name>
```

Dấu hiệu:

```text
ImagePullBackOff
ErrImagePull
rollout bị kẹt
```

Rollback:

```bash
kubectl rollout undo deployment/order-service
kubectl rollout status deployment/order-service
```

### Failure Lab: readiness không pass

Deploy version mới nhưng readiness path sai.

Quan sát:

```bash
kubectl rollout status deployment/order-service
kubectl get pods
kubectl get endpoints order-service
kubectl describe pod <pod-name>
```

Pod mới chạy nhưng không ready, rollout có thể bị kẹt. Đây là hành vi tốt: Kubernetes chưa route traffic sang Pod chưa sẵn sàng.

### Câu hỏi tự kiểm tra

- Rolling update phụ thuộc readiness như thế nào?
- `maxUnavailable` và `maxSurge` khác nhau ra sao?
- Vì sao không nên dùng image `latest`?
- Khi rollout bị kẹt, bạn debug những gì?

## Ngày 15: Graceful Shutdown

### Điều gì xảy ra khi Pod bị terminate?

Pod có thể bị terminate khi:

- rolling update
- scale down
- Node drain
- autoscaling giảm replicas
- bạn xóa Pod

Flow đơn giản:

```text
Kubernetes đánh dấu Pod terminating
Pod bị remove khỏi Service endpoints
Kubernetes gửi SIGTERM vào container
App dừng nhận request/message mới
App hoàn thành request/message đang xử lý
App đóng DB/RabbitMQ connection
App exit
Nếu quá thời gian grace period, Kubernetes gửi SIGKILL
```

### terminationGracePeriodSeconds

```yaml
spec:
  terminationGracePeriodSeconds: 30
```

Ý nghĩa:

```text
App có tối đa 30 giây để shutdown tử tế.
```

Nếu app chưa exit sau thời gian này, container sẽ bị kill mạnh.

### preStop hook

`preStop` là hook chạy trước khi container bị terminate.

Ví dụ:

```yaml
lifecycle:
  preStop:
    exec:
      command: ["sh", "-c", "sleep 10"]
```

`sleep 10` đôi khi được dùng để cho load balancer hoặc proxy có thời gian ngừng route request mới vào Pod.

Không nên lạm dụng `preStop` để che lỗi app. App vẫn cần tự xử lý SIGTERM đúng cách.

### Backend HTTP service nên làm gì?

Khi nhận SIGTERM:

- ngừng nhận request mới
- cho request đang chạy hoàn tất trong một khoảng thời gian hợp lý
- đóng connection pool
- flush log/metrics nếu cần
- exit với status code phù hợp

Readiness nên fail sớm khi app bắt đầu drain, để Service ngừng gửi traffic mới.

### RabbitMQ consumer nên làm gì?

Với RabbitMQ consumer, graceful shutdown đặc biệt quan trọng.

Khi nhận SIGTERM:

- dừng consume message mới
- hoàn thành message đang xử lý nếu có thể
- ACK message đã xử lý xong
- NACK hoặc requeue message chưa xử lý xong
- đóng channel và connection đúng cách
- exit trước khi hết grace period

Điểm cần tránh:

```text
Pod bị kill khi đang xử lý message
Message không ACK/NACK rõ ràng
Hệ thống có thể xử lý trùng hoặc mất kiểm soát trạng thái
```

Tùy cấu hình RabbitMQ, message chưa ACK thường sẽ được requeue khi connection đóng. Nhưng app vẫn nên shutdown có chủ đích để tránh side effect như gọi payment hai lần hoặc cập nhật database nửa chừng.

### Manifest ví dụ

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      terminationGracePeriodSeconds: 45
      containers:
        - name: order-service
          image: ecommerce/order-service:v1
          ports:
            - containerPort: 8000
          lifecycle:
            preStop:
              exec:
                command: ["sh", "-c", "sleep 5"]
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            periodSeconds: 10
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

### Failure Lab

Scale down:

```bash
kubectl scale deployment order-service --replicas=1
kubectl get pods -w
```

Xóa Pod:

```bash
kubectl delete pod <pod-name>
kubectl get pods -w
```

Quan sát events:

```bash
kubectl describe pod <pod-name>
```

Với app thật, thêm log khi nhận SIGTERM để xác nhận graceful shutdown chạy đúng.

### Câu hỏi tự kiểm tra

- Khi Pod terminate, Kubernetes gửi signal gì?
- `terminationGracePeriodSeconds` dùng để làm gì?
- `preStop` có thay thế graceful shutdown trong code không?
- RabbitMQ consumer cần làm gì khi shutdown?

## Bài Thực Hành Tổng Hợp Cuối Tuần

Mục tiêu: cập nhật `Order Service` để vận hành tốt hơn.

### 1. Deployment hoàn chỉnh

Tạo file `order-reliable-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  labels:
    app: order-service
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      terminationGracePeriodSeconds: 45
      containers:
        - name: order-service
          image: ecommerce/order-service:v1
          ports:
            - containerPort: 8000
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 10
            timeoutSeconds: 2
            failureThreshold: 3
          startupProbe:
            httpGet:
              path: /health/startup
              port: 8000
            periodSeconds: 5
            failureThreshold: 30
          lifecycle:
            preStop:
              exec:
                command: ["sh", "-c", "sleep 5"]
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
kubectl apply -f order-reliable-deployment.yaml
kubectl rollout status deployment/order-service
```

### 2. Kiểm tra probes

```bash
kubectl get pods
kubectl describe pod <pod-name>
kubectl get endpoints order-service
```

### 3. Kiểm tra resource config

```bash
kubectl describe pod <pod-name>
kubectl top pods
```

Nếu `kubectl top pods` không chạy được, cluster của bạn chưa có metrics server.

### 4. Thực hành rollout và rollback

Deploy version mới:

```bash
kubectl set image deployment/order-service order-service=ecommerce/order-service:v2
kubectl rollout status deployment/order-service
```

Xem lịch sử:

```bash
kubectl rollout history deployment/order-service
```

Rollback:

```bash
kubectl rollout undo deployment/order-service
kubectl rollout status deployment/order-service
```

### 5. Thực hành failure lab

Làm ít nhất 3 lỗi:

```text
readiness path sai
liveness path sai
image tag không tồn tại
memory limit quá thấp
```

Với mỗi lỗi, debug bằng:

```bash
kubectl get pods
kubectl describe pod <pod-name>
kubectl logs <pod-name>
kubectl get endpoints order-service
kubectl rollout status deployment/order-service
```

## Cheatsheet Tuần 3

### Probes

```bash
kubectl get pods
kubectl describe pod <pod-name>
kubectl get endpoints <service-name>
kubectl logs <pod-name>
```

### Resources

```bash
kubectl describe pod <pod-name>
kubectl top pods
kubectl top nodes
```

### Rollout

```bash
kubectl set image deployment/order-service order-service=ecommerce/order-service:v2
kubectl rollout status deployment/order-service
kubectl rollout history deployment/order-service
kubectl rollout history deployment/order-service --revision=2
kubectl rollout undo deployment/order-service
kubectl rollout undo deployment/order-service --to-revision=1
```

### Debug deployment lifecycle

```bash
kubectl get events --sort-by=.lastTimestamp
kubectl describe deployment order-service
kubectl describe replicaset <replicaset-name>
kubectl describe pod <pod-name>
```

## Những Lỗi Hay Gặp

### Readiness luôn trả 200

Nếu readiness luôn trả 200, Kubernetes có thể route traffic vào Pod chưa thật sự sẵn sàng.

Readiness nên phản ánh khả năng nhận request thật.

### Liveness check quá nặng

Liveness không nên gọi database, RabbitMQ hoặc service bên ngoài.

Nếu dependency tạm thời lỗi, app có thể bị restart hàng loạt.

### Resource limit quá thấp

Memory limit quá thấp dễ gây:

```text
OOMKilled
Exit Code 137
CrashLoopBackOff
```

### Dùng image latest

`latest` làm rollback và audit khó hơn.

Nên dùng tag version rõ ràng.

### Không xử lý SIGTERM

Nếu app không xử lý SIGTERM, request hoặc message đang xử lý có thể bị ngắt giữa chừng.

Với RabbitMQ consumer, đây là lỗi rất dễ tạo duplicate processing hoặc trạng thái không nhất quán.

## Checklist Kết Thúc Tuần

Bạn đã hoàn thành tuần 3 nếu có thể tự trả lời:

- Readiness, liveness, startup probe khác nhau thế nào?
- Readiness fail ảnh hưởng Service endpoints ra sao?
- Liveness fail dẫn đến điều gì?
- Vì sao liveness không nên check database?
- Scheduler dùng request hay limit?
- CPU limit và memory limit khác nhau thế nào?
- OOMKilled là gì?
- Rolling update hoạt động như thế nào?
- `maxUnavailable` và `maxSurge` có ý nghĩa gì?
- Rollback Deployment bằng lệnh nào?
- Khi Pod terminate, app cần làm gì?
- RabbitMQ consumer cần shutdown như thế nào?

Bạn cũng cần tự làm được:

```text
Thêm readinessProbe vào Deployment
Thêm livenessProbe vào Deployment
Thêm startupProbe khi app khởi động chậm
Thêm resources.requests và resources.limits
Thực hiện rolling update
Rollback khi deploy lỗi
Cố tình làm readiness fail và quan sát endpoints
Cố tình làm liveness fail và quan sát restart count
Giải thích graceful shutdown cho HTTP service và RabbitMQ consumer
```

## Đáp Án Gợi Ý Cho Câu Hỏi Tự Kiểm Tra

### Ngày 11

- Readiness khác container running ở chỗ container có thể đang chạy nhưng chưa sẵn sàng nhận traffic. Readiness mới quyết định Pod có vào Service endpoints hay không.
- Nếu readiness fail, Pod không bị restart chỉ vì readiness fail. Nó bị loại khỏi endpoints để không nhận traffic mới.
- Readiness ảnh hưởng Service endpoints vì Kubernetes chỉ đưa Pod ready vào danh sách backend của Service.
- Health endpoint readiness nên kiểm tra những điều kiện thật sự cần để phục vụ request, ví dụ app đã load config, kết nối dependency bắt buộc, hoặc không ở trạng thái draining.

### Ngày 12

- Readiness dùng để báo Pod đã sẵn sàng nhận traffic hay chưa.
- Liveness dùng để báo container có bị treo/hỏng đến mức cần restart hay không.
- Startup probe dùng cho app khởi động chậm để tránh liveness restart app quá sớm.
- Liveness không nên check database vì DB lỗi tạm thời có thể làm nhiều Pod bị restart hàng loạt, tạo restart storm.

### Ngày 13

- Scheduler dùng `requests` để chọn Node phù hợp cho Pod.
- CPU limit thường gây throttling khi vượt giới hạn. Memory limit có thể làm container bị kill với `OOMKilled`.
- Memory limit quá thấp khiến process vượt giới hạn bộ nhớ và bị kernel/Kubernetes kill.
- QoS class ảnh hưởng mức ưu tiên khi Node thiếu tài nguyên. `BestEffort` dễ bị evict hơn `Burstable`, và `Guaranteed` được ưu tiên hơn.

### Ngày 14

- Rolling update phụ thuộc readiness để biết Pod version mới đã đủ sẵn sàng trước khi giảm dần Pod version cũ.
- `maxUnavailable` giới hạn số Pod được phép unavailable trong rollout. `maxSurge` giới hạn số Pod được tạo thêm vượt quá replicas mong muốn.
- Không nên dùng `latest` vì khó biết version thật đang chạy, khó rollback, khó audit và dễ deploy nhầm.
- Khi rollout bị kẹt, kiểm tra `rollout status`, Pod status, events, logs, image pull, readiness probe và endpoints.

### Ngày 15

- Khi Pod terminate, Kubernetes gửi `SIGTERM` cho container, chờ grace period, rồi gửi `SIGKILL` nếu container chưa thoát.
- `terminationGracePeriodSeconds` cho app thời gian shutdown tử tế trước khi bị kill mạnh.
- `preStop` không thay thế graceful shutdown trong code. Nó chỉ là hook hỗ trợ; app vẫn cần xử lý SIGTERM.
- RabbitMQ consumer nên dừng nhận message mới, hoàn tất message đang xử lý nếu có thể, ACK message đã xong, NACK/requeue message chưa xong, đóng channel/connection rồi exit.
