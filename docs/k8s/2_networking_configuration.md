# Tuần 2: Networking Và Configuration

## Mục Tiêu Tuần Này

Sau tuần 2, bạn cần hiểu cách các service trong Kubernetes giao tiếp với nhau và cách tách cấu hình ra khỏi image.

Deliverable cuối tuần:

- deploy được nhiều service nội bộ: `order-service`, `inventory-service`, `payment-service`
- mỗi service có `Deployment` và `ClusterIP Service`
- các service gọi nhau bằng DNS name của Kubernetes
- cấu hình không nhạy cảm nằm trong `ConfigMap`
- thông tin nhạy cảm nằm trong `Secret`
- expose HTTP từ ngoài cluster vào service bằng `Ingress`
- debug được các lỗi network phổ biến: sai selector, sai port, sai DNS, Service không có endpoint

> Ghi chú: Các ví dụ vẫn dùng `nginx:1.27-alpine` để bạn chạy được ngay. Khi áp dụng vào project thật, thay bằng image của từng service.

## Mental Model Tổng Quan

Tuần 1 bạn đã học:

```text
Deployment -> ReplicaSet -> Pods -> Service
```

Tuần 2 thêm ba mảnh quan trọng:

```text
Service DNS
ConfigMap / Secret
Ingress
```

Trong Kubernetes, Pod không nên gọi nhau bằng IP. Pod IP có thể thay đổi bất cứ lúc nào.

Thay vào đó:

```text
Order Service -> http://inventory-service
Order Service -> http://payment-service
Order Service -> rabbitmq
```

Không dùng:

- `localhost` để gọi service khác
- hardcoded Pod IP
- `host.docker.internal` cho giao tiếp service-to-service trong cluster

Điểm cần nhớ:

```text
localhost trong Order Pod chỉ là chính Order Pod.
```

Nếu `Order Service` gọi `http://localhost:8000`, nó đang gọi chính container trong Pod đó, không phải `Inventory Service`.

## Ngày 6: Kubernetes DNS Và Service-To-Service Communication

### Kubernetes DNS hoạt động thế nào?

Khi bạn tạo một `Service`, Kubernetes tạo DNS name cho Service đó.

Nếu Service tên là:

```text
inventory-service
```

trong namespace:

```text
ecommerce
```

thì các Pod trong cùng namespace có thể gọi:

```text
http://inventory-service
```

Tên đầy đủ là:

```text
inventory-service.ecommerce.svc.cluster.local
```

Thông thường trong cùng namespace, bạn chỉ cần dùng short name:

```text
inventory-service
```

### Triển khai 3 service nội bộ

Tạo namespace:

```bash
kubectl create namespace ecommerce
kubectl config set-context --current --namespace=ecommerce
```

Tạo file `services-demo.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  labels:
    app: order-service
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
---
apiVersion: v1
kind: Service
metadata:
  name: order-service
spec:
  type: ClusterIP
  selector:
    app: order-service
  ports:
    - name: http
      port: 80
      targetPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inventory-service
  labels:
    app: inventory-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: inventory-service
  template:
    metadata:
      labels:
        app: inventory-service
    spec:
      containers:
        - name: inventory-service
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: inventory-service
spec:
  type: ClusterIP
  selector:
    app: inventory-service
  ports:
    - name: http
      port: 80
      targetPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
  labels:
    app: payment-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: payment-service
  template:
    metadata:
      labels:
        app: payment-service
    spec:
      containers:
        - name: payment-service
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: payment-service
spec:
  type: ClusterIP
  selector:
    app: payment-service
  ports:
    - name: http
      port: 80
      targetPort: 80
```

Apply:

```bash
kubectl apply -f services-demo.yaml
```

Kiểm tra:

```bash
kubectl get deployments
kubectl get pods -o wide
kubectl get services
kubectl get endpoints
```

### Test DNS từ trong cluster

Chạy một Pod tạm để test network:

```bash
kubectl run debug --rm -it --image=curlimages/curl:8.11.1 -- sh
```

Trong shell của Pod debug:

```sh
curl http://inventory-service
curl http://payment-service
```

Nếu image có `nslookup`, kiểm tra DNS:

```sh
nslookup inventory-service
nslookup payment-service
```

Nếu không có `nslookup`, dùng image khác:

```bash
kubectl run dns-debug --rm -it --image=busybox:1.36 -- sh
```

Trong Pod:

```sh
nslookup inventory-service
```

### Câu hỏi tự kiểm tra

- Vì sao Pod không nên gọi Pod IP của nhau?
- `localhost` trong một Pod nghĩa là gì?
- Service DNS name được tạo từ đâu?
- Khi nào dùng short name `inventory-service`, khi nào cần FQDN?

## Ngày 7: ConfigMap

### ConfigMap là gì?

`ConfigMap` dùng để lưu cấu hình không nhạy cảm.

Ví dụ:

- `LOG_LEVEL`
- `RABBITMQ_HOST`
- `PAYMENT_TIMEOUT_SECONDS`
- feature flag không nhạy cảm
- tên service nội bộ

Không nên hardcode các giá trị này trong image, vì cùng một image nên có thể chạy ở nhiều môi trường khác nhau:

```text
development
staging
production
```

Image nên chứa code. Config nên được inject từ bên ngoài.

### Tạo ConfigMap

Tạo file `order-config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: order-config
data:
  RABBITMQ_HOST: rabbitmq
  LOG_LEVEL: INFO
  PAYMENT_TIMEOUT_SECONDS: "30"
```

Apply:

```bash
kubectl apply -f order-config.yaml
```

Kiểm tra:

```bash
kubectl get configmaps
kubectl describe configmap order-config
```

### Inject ConfigMap bằng envFrom

Cập nhật Deployment:

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
          envFrom:
            - configMapRef:
                name: order-config
```

Apply:

```bash
kubectl apply -f order-deployment.yaml
```

Kiểm tra biến môi trường trong Pod:

```bash
kubectl get pods -l app=order-service
kubectl exec -it <pod-name> -- env
```

### Inject một key cụ thể

Nếu chỉ muốn lấy một key:

```yaml
env:
  - name: LOG_LEVEL
    valueFrom:
      configMapKeyRef:
        name: order-config
        key: LOG_LEVEL
```

### Mount ConfigMap thành file

Một số app đọc config từ file thay vì env.

Ví dụ:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-file
data:
  application.yaml: |
    logLevel: INFO
    paymentTimeoutSeconds: 30
```

Mount vào container:

```yaml
volumes:
  - name: app-config
    configMap:
      name: app-config-file
containers:
  - name: order-service
    image: nginx:1.27-alpine
    volumeMounts:
      - name: app-config
        mountPath: /etc/app-config
```

Kiểm tra:

```bash
kubectl exec -it <pod-name> -- ls /etc/app-config
kubectl exec -it <pod-name> -- cat /etc/app-config/application.yaml
```

### Lưu ý quan trọng khi đổi ConfigMap

Nếu ConfigMap được inject bằng environment variable, Pod thường cần restart để nhận giá trị mới.

Restart rollout:

```bash
kubectl rollout restart deployment/order-service
kubectl rollout status deployment/order-service
```

Nếu ConfigMap được mount thành volume, file có thể được Kubernetes cập nhật sau một khoảng trễ. Nhưng app của bạn vẫn cần tự reload file nếu muốn áp dụng config mới mà không restart.

### Câu hỏi tự kiểm tra

- ConfigMap dùng cho loại dữ liệu nào?
- Vì sao nên tách config khỏi image?
- `envFrom` khác gì `configMapKeyRef`?
- Sau khi đổi ConfigMap dạng env, vì sao thường cần restart Pod?

## Ngày 8: Secret

### Secret là gì?

`Secret` dùng cho dữ liệu nhạy cảm:

- password
- token
- API key
- connection string có credential
- certificate private key

Điểm rất quan trọng:

```text
Base64 không phải encryption.
```

Secret trong Kubernetes mặc định chỉ được encode base64. Nó không tự động trở thành vault.

Trong production, bạn cần quan tâm thêm:

- RBAC để giới hạn ai được đọc Secret
- encryption at rest cho etcd
- không commit secret production vào Git
- external secret manager như Vault, AWS Secrets Manager, Azure Key Vault, Google Secret Manager

### ConfigMap vs Secret

| Loại | Dùng cho |
| --- | --- |
| ConfigMap | Cấu hình không nhạy cảm |
| Secret | Dữ liệu nhạy cảm |

Ví dụ:

```text
LOG_LEVEL -> ConfigMap
DATABASE_HOST -> ConfigMap
DATABASE_PASSWORD -> Secret
JWT_PRIVATE_KEY -> Secret
```

### Tạo Secret bằng stringData

Tạo file `order-secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: order-secret
type: Opaque
stringData:
  DATABASE_PASSWORD: order-password
  DATABASE_USER: order-user
```

`stringData` cho phép viết plain text trong manifest. Kubernetes sẽ encode thành data base64 khi lưu.

Apply:

```bash
kubectl apply -f order-secret.yaml
```

Kiểm tra:

```bash
kubectl get secrets
kubectl describe secret order-secret
```

Không dùng `describe` để xem value. Muốn xem để học local:

```bash
kubectl get secret order-secret -o yaml
```

Decode một key:

```bash
kubectl get secret order-secret -o jsonpath='{.data.DATABASE_PASSWORD}'
```

### Inject Secret vào Deployment

Dùng `envFrom`:

```yaml
envFrom:
  - configMapRef:
      name: order-config
  - secretRef:
      name: order-secret
```

Dùng một key cụ thể:

```yaml
env:
  - name: DATABASE_PASSWORD
    valueFrom:
      secretKeyRef:
        name: order-secret
        key: DATABASE_PASSWORD
```

Kiểm tra trong Pod local lab:

```bash
kubectl exec -it <pod-name> -- env
```

### Câu hỏi tự kiểm tra

- Secret khác ConfigMap ở điểm nào?
- Vì sao base64 không phải encryption?
- Có nên commit Secret production vào Git không?
- Production thường quản lý Secret bằng cách nào?

## Ngày 9: Ingress

### Vì sao cần Ingress?

`Service` loại `ClusterIP` chỉ dùng nội bộ trong cluster.

Nếu muốn request HTTP/HTTPS từ ngoài cluster đi vào application, bạn thường dùng:

```text
Client -> Ingress Controller -> Ingress rule -> Service -> Pod
```

`Ingress` là resource khai báo rule HTTP routing.

`Ingress Controller` là thành phần thực thi rule đó.

Điểm cần nhớ:

```text
Tạo Ingress resource một mình chưa đủ.
Cluster phải có Ingress Controller.
```

Ví dụ Ingress Controller phổ biến:

- NGINX Ingress Controller
- Traefik
- HAProxy Ingress
- cloud provider ingress controller

Với kind, bạn có thể cài NGINX Ingress Controller theo tài liệu chính thức của ingress-nginx.

### Host-based và path-based routing

Host-based routing:

```text
api.local.test -> order-service
admin.local.test -> admin-service
```

Path-based routing:

```text
/api/orders    -> order-service
/api/inventory -> inventory-service
/api/payments  -> payment-service
```

Trong microservices, không phải service nào cũng nên public.

Ví dụ:

```text
Ingress
  -> order-service public API
order-service
  -> inventory-service internal
  -> payment-service internal
  -> rabbitmq internal
```

Inventory và Payment chỉ nên expose ra ngoài nếu thật sự có public API.

### Ingress manifest ví dụ

Tạo file `ecommerce-ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ecommerce-ingress
spec:
  rules:
    - host: ecommerce.local
      http:
        paths:
          - path: /api/orders
            pathType: Prefix
            backend:
              service:
                name: order-service
                port:
                  number: 80
          - path: /api/inventory
            pathType: Prefix
            backend:
              service:
                name: inventory-service
                port:
                  number: 80
          - path: /api/payments
            pathType: Prefix
            backend:
              service:
                name: payment-service
                port:
                  number: 80
```

Apply:

```bash
kubectl apply -f ecommerce-ingress.yaml
```

Kiểm tra:

```bash
kubectl get ingress
kubectl describe ingress ecommerce-ingress
```

### Test Ingress local

Nếu Ingress Controller đã chạy và map về localhost, thêm host vào file hosts của máy:

```text
127.0.0.1 ecommerce.local
```

Test:

```bash
curl http://ecommerce.local/api/orders
curl http://ecommerce.local/api/inventory
curl http://ecommerce.local/api/payments
```

Nếu chưa cài Ingress Controller, bạn vẫn có thể đọc manifest và hiểu flow, nhưng request từ ngoài cluster sẽ chưa hoạt động.

### Câu hỏi tự kiểm tra

- Ingress khác Service ở điểm nào?
- Ingress resource và Ingress Controller khác nhau thế nào?
- Khi nào dùng host-based routing?
- Khi nào dùng path-based routing?
- Vì sao không nên expose tất cả service ra ngoài?

## Ngày 10: Network Failure Lab

Mục tiêu ngày 10 là cố tình phá network để học cách debug.

### Lab 1: Sai Service selector

Service đúng:

```yaml
selector:
  app: order-service
```

Phá bằng cách đổi thành:

```yaml
selector:
  app: order-service-wrong
```

Apply lại:

```bash
kubectl apply -f order-service.yaml
```

Kiểm tra:

```bash
kubectl get endpoints order-service
kubectl describe service order-service
kubectl get pods --show-labels
```

Dấu hiệu:

```text
Service tồn tại nhưng không có endpoint.
```

Sửa lại selector cho khớp label của Pod.

### Lab 2: Sai targetPort

Nếu container listen port `80` nhưng Service trỏ đến `targetPort: 8000`, request sẽ không tới đúng port.

Kiểm tra:

```bash
kubectl describe service order-service
kubectl get pods -l app=order-service -o yaml
```

Sửa:

```yaml
ports:
  - port: 80
    targetPort: 80
```

### Lab 3: Dùng sai DNS name

Trong Pod debug:

```bash
kubectl run debug --rm -it --image=curlimages/curl:8.11.1 -- sh
```

Gọi sai:

```sh
curl http://inventory
```

Gọi đúng:

```sh
curl http://inventory-service
```

Nếu khác namespace:

```sh
curl http://inventory-service.ecommerce.svc.cluster.local
```

### Lab 4: Xóa Service

Xóa Service:

```bash
kubectl delete service order-service
```

Pod vẫn chạy:

```bash
kubectl get pods -l app=order-service
```

Nhưng DNS và virtual IP của Service không còn:

```bash
kubectl get service order-service
```

Apply lại Service:

```bash
kubectl apply -f order-service.yaml
```

### Lệnh debug cần nhớ

```bash
kubectl get services
kubectl get endpoints
kubectl get endpointslices
kubectl describe service order-service
kubectl get pods --show-labels
kubectl exec -it <pod-name> -- env
kubectl exec -it <pod-name> -- sh
kubectl run debug --rm -it --image=curlimages/curl:8.11.1 -- sh
kubectl run dns-debug --rm -it --image=busybox:1.36 -- sh
```

## Bài Thực Hành Tổng Hợp Cuối Tuần

Mục tiêu:

```text
Ingress
  -> order-service
order-service
  -> inventory-service
  -> payment-service
  -> rabbitmq

Config:
  -> ConfigMap
  -> Secret
```

Trong phạm vi tuần 2, bạn có thể mô phỏng bằng `nginx` cho các service HTTP. RabbitMQ có thể chỉ cần hiểu là một service nội bộ được gọi bằng DNS name `rabbitmq`.

### 1. Tạo namespace

```bash
kubectl create namespace ecommerce
kubectl config set-context --current --namespace=ecommerce
```

### 2. Deploy 3 service nội bộ

Apply file `services-demo.yaml` đã tạo ở ngày 6:

```bash
kubectl apply -f services-demo.yaml
```

### 3. Tạo ConfigMap

```bash
kubectl apply -f order-config.yaml
```

### 4. Tạo Secret

```bash
kubectl apply -f order-secret.yaml
```

### 5. Gắn ConfigMap và Secret vào Order Deployment

Deployment của `order-service` cần có:

```yaml
envFrom:
  - configMapRef:
      name: order-config
  - secretRef:
      name: order-secret
```

Restart rollout nếu cần:

```bash
kubectl rollout restart deployment/order-service
kubectl rollout status deployment/order-service
```

### 6. Test service-to-service DNS

```bash
kubectl run debug --rm -it --image=curlimages/curl:8.11.1 -- sh
```

Trong Pod debug:

```sh
curl http://order-service
curl http://inventory-service
curl http://payment-service
```

### 7. Tạo Ingress

Nếu cluster đã có Ingress Controller:

```bash
kubectl apply -f ecommerce-ingress.yaml
kubectl get ingress
```

Nếu chưa có Ingress Controller, bạn chỉ cần hiểu manifest và flow. Tuần sau có thể quay lại test kỹ hơn khi môi trường đã sẵn sàng.

## Cheatsheet Tuần 2

### Service và DNS

```bash
kubectl get services
kubectl get endpoints
kubectl get endpointslices
kubectl describe service <service-name>
kubectl run debug --rm -it --image=curlimages/curl:8.11.1 -- sh
kubectl run dns-debug --rm -it --image=busybox:1.36 -- sh
```

### ConfigMap

```bash
kubectl get configmaps
kubectl describe configmap <configmap-name>
kubectl create configmap order-config --from-literal=LOG_LEVEL=INFO
kubectl rollout restart deployment/order-service
```

### Secret

```bash
kubectl get secrets
kubectl describe secret <secret-name>
kubectl create secret generic order-secret --from-literal=DATABASE_PASSWORD=order-password
kubectl get secret order-secret -o yaml
```

### Ingress

```bash
kubectl get ingress
kubectl describe ingress <ingress-name>
```

## Checklist Kết Thúc Tuần

Bạn đã hoàn thành tuần 2 nếu có thể tự trả lời:

- Service DNS hoạt động như thế nào?
- Vì sao không dùng `localhost` để gọi service khác?
- Vì sao không hardcode Pod IP?
- ConfigMap dùng cho dữ liệu gì?
- Secret dùng cho dữ liệu gì?
- Vì sao base64 không phải encryption?
- Ingress resource khác Ingress Controller như thế nào?
- Service không có endpoint thì debug ở đâu?
- Sai `selector` và sai `targetPort` khác nhau thế nào?

Bạn cũng cần tự làm được:

```text
Deploy order-service, inventory-service, payment-service
Expose mỗi service bằng ClusterIP
Gọi service bằng DNS name từ trong cluster
Inject config bằng ConfigMap
Inject secret bằng Secret
Tạo Ingress rule cơ bản
Cố tình phá selector, targetPort, DNS và tự debug
```

## Đáp Án Gợi Ý Cho Câu Hỏi Tự Kiểm Tra

### Ngày 6

- Pod không nên gọi Pod IP của nhau vì Pod IP là ephemeral. Khi Pod bị xóa hoặc reschedule, IP có thể đổi.
- `localhost` trong một Pod là chính network namespace của Pod đó. Nó không trỏ đến service khác trong cluster.
- Service DNS name được tạo từ tên Service và namespace, ví dụ `inventory-service.ecommerce.svc.cluster.local`.
- Trong cùng namespace có thể dùng short name như `inventory-service`. Khi gọi khác namespace, nên dùng tên đầy đủ hơn như `inventory-service.ecommerce.svc.cluster.local` hoặc ít nhất `inventory-service.ecommerce`.

### Ngày 7

- ConfigMap dùng cho cấu hình không nhạy cảm như log level, timeout, tên host nội bộ, feature flag không bí mật.
- Nên tách config khỏi image để cùng một image có thể chạy ở dev/staging/prod với cấu hình khác nhau.
- `envFrom` inject toàn bộ key trong ConfigMap thành environment variables. `configMapKeyRef` chỉ lấy một key cụ thể.
- Sau khi đổi ConfigMap dạng env, Pod thường cần restart vì environment variables được set khi container start, không tự đổi trong process đang chạy.

### Ngày 8

- Secret dùng cho dữ liệu nhạy cảm, ConfigMap dùng cho dữ liệu không nhạy cảm.
- Base64 không phải encryption vì ai có dữ liệu base64 đều có thể decode ngược lại dễ dàng.
- Không nên commit Secret production vào Git. Local lab có thể dùng ví dụ đơn giản, production thì không.
- Production thường dùng external secret manager, External Secrets Operator, sealed secrets hoặc CI/CD secret injection, kèm RBAC và encryption at rest.

### Ngày 9

- Service expose network nội bộ hoặc kiểu load balancing tới Pod. Ingress định nghĩa rule HTTP/HTTPS từ ngoài cluster vào Service.
- Ingress resource chỉ là cấu hình rule. Ingress Controller là component thật sự nhận traffic và thực thi rule đó.
- Host-based routing dùng khi muốn route theo domain/subdomain, ví dụ `api.example.com` và `admin.example.com`.
- Path-based routing dùng khi nhiều route HTTP chung một host, ví dụ `/api/orders` và `/api/payments`.
- Không nên expose tất cả service ra ngoài vì tăng attack surface, rò rỉ internal API và làm kiến trúc khó kiểm soát hơn.

### Ngày 10

- Service không có endpoint thường do selector không match label Pod, Pod chưa ready, hoặc resource nằm khác namespace.
- Sai selector làm Service không chọn được Pod nào. Sai `targetPort` có thể vẫn có endpoint nhưng traffic đi tới port sai trên Pod.
- Sai DNS name thường gây lỗi resolve host hoặc gọi nhầm Service. Debug bằng Pod tạm với `curl`/`nslookup`.
- Xóa Service không làm Pod chết, nhưng DNS name, virtual IP và routing qua Service sẽ biến mất.
