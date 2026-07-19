# Tuần 5: Helm, Observability Và Production Readiness

## Mục Tiêu Tuần Này

Tuần 5 gom các phần bạn cần để đưa manifest rời rạc thành một cách triển khai có tổ chức hơn, dễ cấu hình theo môi trường hơn, và dễ vận hành hơn.

Deliverable cuối tuần:

- hiểu Helm fundamentals: Chart, template, values, release, install, upgrade, rollback
- tạo được Helm chart cơ bản cho ecommerce services
- tách được cấu hình `dev`, `staging`, `prod` bằng values file
- có quy trình debug Kubernetes rõ ràng
- biết nhóm metric quan trọng cho microservices
- chuẩn bị được một bộ manifest/chart production-ready ở mức nền tảng

> Ghi chú: Không nên học Helm trước khi hiểu manifest YAML. Helm chỉ có ý nghĩa khi bạn đã thấy việc copy/paste manifest giữa nhiều service và nhiều môi trường bắt đầu gây đau.

## Mental Model Tổng Quan

Trước Helm, bạn có nhiều file YAML:

```text
order-deployment.yaml
order-service.yaml
inventory-deployment.yaml
inventory-service.yaml
payment-deployment.yaml
payment-service.yaml
ingress.yaml
hpa.yaml
configmap.yaml
secret.yaml
```

Khi số service và môi trường tăng lên, bạn dễ gặp vấn đề:

- copy manifest nhiều lần
- quên sửa image tag ở một môi trường
- dev/staging/prod khác nhau nhưng không rõ khác ở đâu
- rollback thủ công khó
- cấu hình bị phân tán

Helm giúp đóng gói manifest thành chart:

```text
Chart + values -> render thành Kubernetes manifests -> install/upgrade vào cluster
```

Helm không thay thế Kubernetes. Helm là package manager/template engine cho Kubernetes manifests.

## Ngày 21: Helm Fundamentals

### Các khái niệm chính

| Khái niệm | Ý nghĩa |
| --- | --- |
| Chart | Gói Helm chứa template và metadata. |
| `values.yaml` | File cấu hình mặc định cho chart. |
| Template | YAML có biến, render ra manifest Kubernetes. |
| Release | Một lần install chart vào cluster. |
| `helm install` | Cài release mới. |
| `helm upgrade` | Nâng cấp release. |
| `helm rollback` | Quay lại revision cũ của release. |

### Cấu trúc chart

```text
helm/ecommerce/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    ├── hpa.yaml
    ├── configmap.yaml
    └── secret.yaml
```

Tạo chart:

```bash
helm create ecommerce
```

Hoặc tự tạo cấu trúc tối giản nếu muốn học rõ từng file.

### Chart.yaml

```yaml
apiVersion: v2
name: ecommerce
description: Ecommerce microservices chart
type: application
version: 0.1.0
appVersion: "1.0.0"
```

### values.yaml

```yaml
services:
  order:
    name: order-service
    image:
      repository: ecommerce/order-service
      tag: v1
    replicas: 2
    port: 8000
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 512Mi

config:
  LOG_LEVEL: INFO
  RABBITMQ_HOST: rabbitmq

ingress:
  enabled: true
  host: ecommerce.local
```

### Template Deployment đơn giản

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.services.order.name }}
spec:
  replicas: {{ .Values.services.order.replicas }}
  selector:
    matchLabels:
      app: {{ .Values.services.order.name }}
  template:
    metadata:
      labels:
        app: {{ .Values.services.order.name }}
    spec:
      containers:
        - name: {{ .Values.services.order.name }}
          image: "{{ .Values.services.order.image.repository }}:{{ .Values.services.order.image.tag }}"
          ports:
            - containerPort: {{ .Values.services.order.port }}
          resources:
            {{- toYaml .Values.services.order.resources | nindent 12 }}
```

### Lệnh Helm cơ bản

Render template để kiểm tra trước:

```bash
helm template ecommerce ./helm/ecommerce
```

Install:

```bash
helm install ecommerce ./helm/ecommerce -n ecommerce --create-namespace
```

Upgrade:

```bash
helm upgrade ecommerce ./helm/ecommerce -n ecommerce
```

Xem release:

```bash
helm list -n ecommerce
helm status ecommerce -n ecommerce
helm history ecommerce -n ecommerce
```

Rollback:

```bash
helm rollback ecommerce 1 -n ecommerce
```

Uninstall:

```bash
helm uninstall ecommerce -n ecommerce
```

### Câu hỏi tự kiểm tra

- Chart khác release ở điểm nào?
- `values.yaml` dùng để làm gì?
- Vì sao nên chạy `helm template` trước khi install/upgrade?
- Helm rollback khác `kubectl rollout undo` ở điểm nào?

## Ngày 22: Environment Separation

### Vì sao cần tách môi trường?

Dev, staging và production thường khác nhau ở:

- replicas
- resource requests/limits
- log level
- ingress host
- HPA min/max
- external dependencies
- secret source
- feature flags

Không nên copy toàn bộ manifest cho từng môi trường.

Nên dùng một chart chung:

```text
helm/ecommerce/
```

và nhiều values file:

```text
values-dev.yaml
values-staging.yaml
values-prod.yaml
```

### values-dev.yaml

```yaml
services:
  order:
    replicas: 1
    image:
      tag: dev
    resources:
      requests:
        cpu: 50m
        memory: 64Mi
      limits:
        cpu: 250m
        memory: 256Mi

config:
  LOG_LEVEL: DEBUG

ingress:
  host: dev.ecommerce.local

hpa:
  enabled: false
```

### values-staging.yaml

```yaml
services:
  order:
    replicas: 2
    image:
      tag: staging

config:
  LOG_LEVEL: INFO

ingress:
  host: staging.ecommerce.example.com

hpa:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
```

### values-prod.yaml

```yaml
services:
  order:
    replicas: 3
    image:
      tag: v1.0.0
    resources:
      requests:
        cpu: 250m
        memory: 256Mi
      limits:
        cpu: 1000m
        memory: 1Gi

config:
  LOG_LEVEL: WARN

ingress:
  host: api.ecommerce.example.com

hpa:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
```

### Deploy theo môi trường

Dev:

```bash
helm upgrade --install ecommerce ./helm/ecommerce -n ecommerce-dev --create-namespace -f values-dev.yaml
```

Staging:

```bash
helm upgrade --install ecommerce ./helm/ecommerce -n ecommerce-staging --create-namespace -f values-staging.yaml
```

Production:

```bash
helm upgrade --install ecommerce ./helm/ecommerce -n ecommerce-prod --create-namespace -f values-prod.yaml
```

### Không để secret production plain text trong values

Không nên commit:

```yaml
databasePassword: real-prod-password
```

Production nên dùng:

- external secret manager
- sealed secrets
- CI/CD secret injection
- External Secrets Operator

### Câu hỏi tự kiểm tra

- Vì sao không nên copy manifest cho từng môi trường?
- Những field nào thường khác nhau giữa dev/staging/prod?
- Có nên commit secret production vào values file không?
- `helm upgrade --install` có ý nghĩa gì?

## Ngày 23: Logging Và Debugging

### Các lệnh phải thành thạo

```bash
kubectl get pods
kubectl describe pod <pod-name>
kubectl logs <pod-name>
kubectl logs <pod-name> --previous
kubectl exec -it <pod-name> -- sh
kubectl top pods
kubectl get events --sort-by=.lastTimestamp
kubectl get endpoints
kubectl rollout status deployment/<deployment-name>
```

### Quy trình debug chuẩn

Khi service lỗi, đi theo thứ tự:

```text
1. Pod có tồn tại không?
2. Pod phase là gì?
3. Container READY không?
4. Event báo gì?
5. Logs hiện tại nói gì?
6. Logs previous có gì nếu container restart?
7. Service có endpoint không?
8. DNS hoạt động không?
9. ConfigMap/Secret đúng không?
10. Dependency có reachable không?
11. Rollout có bị kẹt không?
```

### Pod không chạy

Kiểm tra:

```bash
kubectl get pods
kubectl describe pod <pod-name>
```

Các trạng thái hay gặp:

| Trạng thái | Ý nghĩa thường gặp |
| --- | --- |
| Pending | Chưa schedule được, thiếu resource hoặc PVC chưa bind. |
| ImagePullBackOff | Kéo image thất bại. |
| CrashLoopBackOff | App start rồi crash lặp lại. |
| Running nhưng READY 0/1 | Container chạy nhưng readiness fail. |
| OOMKilled | Container vượt memory limit. |

### Logs

Logs hiện tại:

```bash
kubectl logs <pod-name>
```

Logs container trước đó:

```bash
kubectl logs <pod-name> --previous
```

Dùng khi container restart và logs hiện tại không còn đủ thông tin.

### Service không có traffic

Kiểm tra Service và endpoints:

```bash
kubectl get service order-service
kubectl describe service order-service
kubectl get endpoints order-service
kubectl get pods --show-labels
```

Nếu endpoints rỗng, thường do:

- Service selector không match label Pod
- Pod chưa ready
- Pod ở namespace khác

### Debug từ trong cluster

```bash
kubectl run debug --rm -it --image=curlimages/curl:8.11.1 -- sh
```

Trong Pod debug:

```sh
curl http://order-service
curl http://inventory-service
```

DNS debug:

```bash
kubectl run dns-debug --rm -it --image=busybox:1.36 -- sh
```

Trong Pod:

```sh
nslookup order-service
```

### Câu hỏi tự kiểm tra

- Khi Pod `CrashLoopBackOff`, bạn xem gì đầu tiên?
- Khi Service không có endpoint, nguyên nhân thường là gì?
- `kubectl logs --previous` dùng khi nào?
- Vì sao cần debug từ trong cluster?

## Ngày 24: Metrics Và Observability

### Observability là gì?

Observability giúp bạn trả lời:

```text
Hệ thống đang khỏe không?
Nếu không khỏe, vì sao?
Người dùng bị ảnh hưởng như thế nào?
Bottleneck nằm ở app, database, message broker hay network?
```

Ba nhóm tín hiệu phổ biến:

- logs
- metrics
- traces

Tuần này chỉ cần nắm mức ứng dụng và Kubernetes cơ bản, chưa cần dựng hệ thống quá lớn.

### Kubernetes metrics cần biết

- Pod CPU
- Pod memory
- restart count
- Pod readiness
- rollout status
- HPA current metric
- Node resource usage

Lệnh:

```bash
kubectl top pods
kubectl top nodes
kubectl get pods
kubectl describe hpa order-service
```

### Application metrics quan trọng

Với HTTP service:

- request rate
- error rate
- latency p50/p95/p99
- status code 4xx/5xx
- in-flight requests
- dependency latency

Với RabbitMQ/event-driven service:

- queue depth
- consumer lag
- DLQ count
- message publish rate
- message consume rate
- retry count
- processing duration

Với saga/outbox:

- outbox backlog
- outbox publish failure
- saga failure count
- stuck saga count
- reconciliation job duration

### Prometheus và Grafana

Ở mức căn bản:

- Prometheus scrape metrics từ app và Kubernetes components
- Grafana hiển thị dashboard
- Alertmanager gửi alert

Bạn không cần dựng observability platform lớn ngay. Nhưng bạn cần biết metric nào phản ánh health của microservice.

### Alert nên gắn với triệu chứng người dùng

Alert tốt:

```text
HTTP 5xx tăng cao
p95 latency vượt ngưỡng
queue depth tăng liên tục
consumer không consume message
Pod restart liên tục
rollout bị kẹt
```

Alert kém:

```text
CPU cao trong vài giây
log có chữ warning bất kỳ
metric nhiễu không ảnh hưởng user
```

### Câu hỏi tự kiểm tra

- Logs, metrics, traces khác nhau thế nào?
- Với HTTP API, metric nào quan trọng nhất?
- Với RabbitMQ consumer, metric nào quan trọng nhất?
- Queue depth tăng liên tục nói lên điều gì?
- Vì sao alert nên gắn với user impact?

## Ngày 25: Final Migration

### Mục tiêu migration

Chuyển toàn bộ project sang một bộ manifest hoặc Helm chart hoàn chỉnh:

```text
order-service
inventory-service
payment-service
notification-service
RabbitMQ
PostgreSQL
Ingress
ConfigMaps
Secrets
PVCs
HPA
Jobs/CronJobs
```

Nếu đang học, có thể dùng một nhóm manifest rõ ràng trước. Nếu số file bắt đầu lặp lại nhiều, chuyển sang Helm.

### Cấu trúc thư mục gợi ý

```text
k8s/
├── base/
│   ├── namespace.yaml
│   ├── order-deployment.yaml
│   ├── order-service.yaml
│   ├── inventory-deployment.yaml
│   ├── inventory-service.yaml
│   ├── payment-deployment.yaml
│   ├── payment-service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── hpa.yaml
│   └── cronjobs.yaml
└── README.md
```

Helm structure:

```text
helm/ecommerce/
├── Chart.yaml
├── values.yaml
├── values-dev.yaml
├── values-staging.yaml
├── values-prod.yaml
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    ├── configmap.yaml
    ├── hpa.yaml
    ├── cronjob.yaml
    └── NOTES.txt
```

### Production readiness checklist

Mỗi service nên có:

- image tag rõ ràng, không dùng `latest`
- readiness probe
- liveness probe
- startup probe nếu cần
- resource requests/limits
- ConfigMap/Secret tách khỏi image
- Service đúng selector
- HPA nếu phù hợp
- rolling update strategy
- graceful shutdown
- logs có correlation/request id nếu là HTTP service
- metrics cơ bản

Với dependency:

- PostgreSQL/RabbitMQ trong lab có PVC
- production ưu tiên managed service hoặc operator
- backup/restore rõ ràng
- credential không commit vào Git

### Dry-run và validate

Render Helm:

```bash
helm template ecommerce ./helm/ecommerce -f values-dev.yaml
```

Lint chart:

```bash
helm lint ./helm/ecommerce
```

Server-side dry run:

```bash
kubectl apply --dry-run=server -f k8s/base/
```

Với Helm:

```bash
helm upgrade --install ecommerce ./helm/ecommerce -n ecommerce --create-namespace -f values-dev.yaml --dry-run
```

### Deploy flow gợi ý

```text
1. Render/validate manifests
2. Deploy vào dev
3. Chạy smoke test
4. Deploy staging
5. Chạy integration test
6. Deploy production
7. Theo dõi rollout, metrics, logs
8. Rollback nếu health check fail
```

Lệnh quan sát sau deploy:

```bash
kubectl rollout status deployment/order-service
kubectl get pods
kubectl get events --sort-by=.lastTimestamp
kubectl get hpa
kubectl get endpoints
```

### Câu hỏi tự kiểm tra

- Khi nào nên chuyển từ manifest rời rạc sang Helm?
- Production readiness của một backend service gồm những gì?
- Vì sao cần dry-run trước khi deploy?
- Sau deploy cần quan sát những gì?

## Bài Thực Hành Tổng Hợp Cuối Tuần

Mục tiêu: đóng gói hệ thống ecommerce thành một Helm chart hoặc một thư mục manifest hoàn chỉnh.

Các bước:

```text
1. Gom manifest của các service vào một cấu trúc rõ ràng
2. Tách biến môi trường vào ConfigMap/Secret
3. Thêm probes và resources cho từng service
4. Thêm Service cho từng service
5. Thêm Ingress cho public API
6. Thêm HPA cho stateless service phù hợp
7. Thêm CronJob cho reconciliation/cleanup
8. Render hoặc dry-run để kiểm tra
9. Deploy vào namespace dev
10. Chạy smoke test và debug nếu lỗi
```

Smoke test gợi ý:

```bash
kubectl get all
kubectl get endpoints
kubectl rollout status deployment/order-service
kubectl port-forward service/order-service 8080:80
```

Nếu có Ingress:

```bash
curl http://ecommerce.local/api/orders
```

## Cheatsheet Tuần 5

### Helm

```bash
helm create ecommerce
helm template ecommerce ./helm/ecommerce
helm lint ./helm/ecommerce
helm install ecommerce ./helm/ecommerce -n ecommerce --create-namespace
helm upgrade ecommerce ./helm/ecommerce -n ecommerce
helm upgrade --install ecommerce ./helm/ecommerce -n ecommerce --create-namespace -f values-dev.yaml
helm list -n ecommerce
helm status ecommerce -n ecommerce
helm history ecommerce -n ecommerce
helm rollback ecommerce 1 -n ecommerce
helm uninstall ecommerce -n ecommerce
```

### Debug

```bash
kubectl get pods
kubectl describe pod <pod-name>
kubectl logs <pod-name>
kubectl logs <pod-name> --previous
kubectl exec -it <pod-name> -- sh
kubectl get events --sort-by=.lastTimestamp
kubectl get endpoints
kubectl rollout status deployment/<deployment-name>
```

### Metrics

```bash
kubectl top pods
kubectl top nodes
kubectl describe hpa <hpa-name>
```

## Những Lỗi Hay Gặp

### Helm template render sai indentation

YAML rất nhạy indentation. Dùng:

```bash
helm template ecommerce ./helm/ecommerce
helm lint ./helm/ecommerce
```

### Values bị override nhầm

Luôn kiểm tra file values đang dùng:

```bash
helm upgrade --install ecommerce ./helm/ecommerce -f values-prod.yaml --dry-run
```

### Copy secret vào values-prod.yaml

Không commit secret production vào Git. Dùng secret manager hoặc cơ chế inject secret từ CI/CD.

### Debug không theo quy trình

Đừng nhảy ngay vào sửa YAML. Đi theo flow:

```text
Pod -> Events -> Logs -> Service endpoints -> DNS -> Config/Secret -> Dependency -> Rollout
```

### Có metrics nhưng không biết đọc

Metric chỉ hữu ích khi trả lời được câu hỏi vận hành. Với microservice, ưu tiên request rate, error rate, latency, restart count, queue depth, DLQ và backlog.

## Checklist Kết Thúc Tuần

Bạn đã hoàn thành tuần 5 nếu có thể tự trả lời:

- Helm Chart, values, template, release khác nhau thế nào?
- `helm install`, `helm upgrade`, `helm rollback` dùng khi nào?
- Vì sao cần values-dev/staging/prod?
- Có nên copy manifest cho từng môi trường không?
- Quy trình debug Kubernetes service lỗi gồm những bước nào?
- Metric nào quan trọng cho HTTP service?
- Metric nào quan trọng cho RabbitMQ consumer?
- Production readiness checklist của service gồm những gì?
- Sau deploy cần quan sát gì để quyết định rollout thành công hay rollback?

Bạn cũng cần tự làm được:

```text
Tạo Helm chart cơ bản
Render manifest bằng helm template
Deploy bằng helm upgrade --install
Tách config theo môi trường bằng values file
Rollback một release
Debug Pod crash bằng describe/logs/events
Debug Service không có endpoint
Liệt kê metric quan trọng cho từng service
Hoàn thiện bộ manifest/chart cuối khóa cho ecommerce project
```

## Đáp Án Gợi Ý Cho Câu Hỏi Tự Kiểm Tra

### Ngày 21

- Chart là gói template và metadata. Release là một lần chart được install vào cluster với một bộ values cụ thể.
- `values.yaml` chứa giá trị cấu hình mặc định để template render ra manifest Kubernetes.
- Nên chạy `helm template` trước khi install/upgrade để xem YAML cuối cùng, bắt lỗi indentation, biến sai hoặc resource render không đúng.
- `helm rollback` rollback toàn bộ release Helm theo revision của Helm. `kubectl rollout undo` chỉ rollback một Deployment cụ thể.

### Ngày 22

- Không nên copy manifest cho từng môi trường vì dễ drift, sửa thiếu, khác biệt không rõ và khó bảo trì.
- Các field thường khác giữa môi trường gồm replicas, resources, log level, ingress host, HPA, external dependencies, image tag và secret source.
- Không nên commit secret production vào values file. Nên dùng secret manager hoặc cơ chế inject secret an toàn.
- `helm upgrade --install` nghĩa là nếu release chưa tồn tại thì install, nếu đã tồn tại thì upgrade. Lệnh này phù hợp cho CI/CD.

### Ngày 23

- Khi Pod `CrashLoopBackOff`, nên xem `kubectl describe pod`, `kubectl logs`, và nếu container đã restart thì xem `kubectl logs --previous`.
- Service không có endpoint thường do selector không match label Pod, Pod chưa ready hoặc sai namespace.
- `kubectl logs --previous` dùng để xem logs của container instance trước đó sau khi container restart.
- Debug từ trong cluster giúp kiểm tra DNS, Service routing và network giống góc nhìn của Pod thật, thay vì chỉ test từ máy local.

### Ngày 24

- Logs là sự kiện dạng text theo thời gian. Metrics là số đo định lượng như latency/error rate/CPU. Traces theo dõi một request đi qua nhiều service.
- Với HTTP API, metric quan trọng gồm request rate, error rate, latency p95/p99, status code 5xx và dependency latency.
- Với RabbitMQ consumer, metric quan trọng gồm queue depth, consumer lag, DLQ count, consume rate, retry count và processing duration.
- Queue depth tăng liên tục thường cho thấy producer gửi nhanh hơn consumer xử lý, consumer lỗi, downstream chậm hoặc concurrency không đủ.
- Alert nên gắn với user impact để tránh nhiễu. CPU cao ngắn hạn chưa chắc là lỗi, nhưng 5xx tăng hoặc latency p95 cao thì ảnh hưởng người dùng rõ hơn.

### Ngày 25

- Nên chuyển từ manifest rời rạc sang Helm khi có nhiều service/môi trường, nhiều giá trị lặp lại, cần release/rollback rõ ràng và muốn giảm copy/paste YAML.
- Production readiness của backend service gồm image tag rõ ràng, probes, resources, config/secret tách riêng, Service đúng selector, rollout strategy, graceful shutdown, logging, metrics và rollback plan.
- Dry-run trước deploy giúp phát hiện YAML sai, resource không hợp lệ hoặc template render sai trước khi thay đổi cluster thật.
- Sau deploy cần quan sát rollout status, Pod readiness, events, logs, endpoints, HPA, error rate, latency, restart count và các metric dependency quan trọng.
