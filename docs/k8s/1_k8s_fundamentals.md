# Tuần 1: Kubernetes Fundamentals

## Mục tiêu tuần này

Sau tuần 1, bạn cần hiểu Kubernetes đang quản lý cái gì và tự deploy được một service đơn giản theo flow production cơ bản:

```text
Deployment -> ReplicaSet -> Pods -> Service
```

Deliverable cuối tuần:

- deploy được `Order Service` bằng `Deployment`
- chạy được 3 Pod của service đó
- expose service bằng `ClusterIP Service`
- biết dùng `kubectl` để kiểm tra, debug và quan sát self-healing
- giải thích được các khái niệm: Cluster, Node, Control Plane, Pod, Deployment, ReplicaSet, Service, Label, Selector, Namespace

> Ghi chú: Các ví dụ dùng image `nginx:1.27-alpine` để bạn chạy được ngay. Khi áp dụng vào project ecommerce thật, thay image này bằng image service của bạn, ví dụ `ecommerce/order-service:local`.

## Chuẩn bị môi trường

Bạn cần có:

- Docker hoặc container runtime tương thích để chạy local cluster
- `kubectl`
- `kind`

Tạo cluster local:

```bash
kind create cluster --name ecommerce
```

Kiểm tra cluster:

```bash
kubectl cluster-info
kubectl get nodes
kubectl version
```

Nếu muốn xóa cluster sau khi học xong:

```bash
kind delete cluster --name ecommerce
```

## Mental Model Tổng Quan

Docker Compose thường trả lời câu hỏi:

```text
Làm sao chạy nhiều container trên một máy?
```

Kubernetes trả lời câu hỏi lớn hơn:

```text
Làm sao giữ nhiều workload container chạy đúng trạng thái mong muốn trên một cluster?
```

Điểm quan trọng nhất của Kubernetes là **desired state**.

Bạn không bảo Kubernetes từng bước phải làm gì. Bạn khai báo trạng thái mong muốn:

```text
Tôi muốn có 3 replica của Order Service.
Service này listen port 8000.
Các Pod có label app=order-service.
Traffic nội bộ đi qua Service order-service.
```

Kubernetes liên tục so sánh:

```text
desired state: trạng thái bạn muốn
actual state: trạng thái thực tế của cluster
```

Nếu lệch nhau, Kubernetes cố gắng kéo actual state về desired state.

Ví dụ:

```text
Bạn muốn 3 Pod
Thực tế chỉ còn 2 Pod vì 1 Pod crash
Kubernetes tạo Pod mới để quay lại 3 Pod
```

## Ngày 1: Cluster, Node và Control Plane

### Cần hiểu gì?

Một Kubernetes cluster gồm hai nhóm chính:

- **Control Plane**: bộ não điều khiển cluster
- **Worker Node**: nơi workload thật sự chạy

Các thành phần quan trọng:

| Thành phần | Vai trò |
| --- | --- |
| API Server | Cổng giao tiếp trung tâm của Kubernetes. `kubectl` nói chuyện với API Server. |
| etcd | Database lưu trạng thái cluster. |
| Scheduler | Chọn Node phù hợp để chạy Pod mới. |
| Controller Manager | Chạy các controller để giữ desired state. |
| kubelet | Agent trên mỗi Node, nhận lệnh và đảm bảo container chạy đúng. |
| kube-proxy | Hỗ trợ networking cho Service. |
| Container runtime | Thành phần thật sự chạy container, ví dụ `containerd` hoặc CRI-O. |

### Flow khi bạn apply manifest

Khi bạn chạy:

```bash
kubectl apply -f deployment.yaml
```

Flow đơn giản là:

```text
kubectl gửi manifest
  -> API Server nhận request
  -> API Server validate và lưu desired state vào etcd
  -> Controller thấy cần tạo Pod
  -> Scheduler chọn Node cho Pod
  -> kubelet trên Node nhận nhiệm vụ
  -> container runtime chạy container
  -> controller tiếp tục quan sát và sửa lệch trạng thái
```

### Thực hành

Tạo cluster:

```bash
kind create cluster --name ecommerce
```

Kiểm tra thông tin cluster:

```bash
kubectl cluster-info
kubectl get nodes
kubectl get nodes -o wide
```

Xem các Pod hệ thống:

```bash
kubectl get pods -n kube-system
```

### Câu hỏi tự kiểm tra

- Kubernetes quản lý desired state như thế nào?
- API Server làm nhiệm vụ gì?
- Scheduler và kubelet khác nhau ở đâu?
- Container runtime có phải là Kubernetes không?

## Ngày 2: Pod

### Pod là gì?

**Pod** là đơn vị deploy nhỏ nhất trong Kubernetes.

Một Pod có thể chứa một hoặc nhiều container. Trong thực tế backend service thông thường, mỗi Pod thường chứa một container chính.

Các container trong cùng một Pod chia sẻ:

- network namespace
- IP address
- port space
- volume được khai báo trong Pod

Nghĩa là nếu một Pod có 2 container, chúng có thể gọi nhau qua `localhost`.

### Pod là tài nguyên tạm thời

Pod không nên được xem là server cố định. Pod có thể bị xóa, bị thay thế, bị schedule sang Node khác. Vì vậy:

- không nên gọi trực tiếp Pod IP
- không nên lưu dữ liệu quan trọng vào filesystem tạm của Pod
- không nên quản lý Pod trực tiếp trong production

Trong production, bạn thường dùng `Deployment` để quản lý Pod.

### Tạo Pod đầu tiên

Tạo file `order-pod.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: order-service
  labels:
    app: order-service
spec:
  containers:
    - name: order-service
      image: nginx:1.27-alpine
      ports:
        - containerPort: 80
```

Apply manifest:

```bash
kubectl apply -f order-pod.yaml
```

Kiểm tra:

```bash
kubectl get pods
kubectl get pods -o wide
kubectl describe pod order-service
kubectl logs order-service
```

Vào shell trong container:

```bash
kubectl exec -it order-service -- sh
```

Expose tạm để test từ máy local:

```bash
kubectl port-forward pod/order-service 8080:80
```

Sau đó mở:

```text
http://localhost:8080
```

### Failure Lab

Xóa Pod:

```bash
kubectl delete pod order-service
```

Kiểm tra lại:

```bash
kubectl get pods
```

Bạn sẽ thấy Pod không tự quay lại, vì bạn tạo Pod trực tiếp. Không có controller nào đứng phía sau để đảm bảo Pod đó luôn tồn tại.

Đây là lý do cần `Deployment`.

### Câu hỏi tự kiểm tra

- Vì sao Pod được xem là tài nguyên tạm thời?
- Vì sao không nên gọi Pod IP trực tiếp?
- Một Pod có thể có nhiều container không?
- Vì sao xóa Pod trực tiếp thì Pod không tự quay lại?

## Ngày 3: Deployment và ReplicaSet

### Deployment là gì?

**Deployment** là resource phổ biến nhất để chạy stateless application trong Kubernetes.

Deployment quản lý `ReplicaSet`, ReplicaSet quản lý `Pod`.

```text
Deployment
  -> ReplicaSet
    -> Pod
    -> Pod
    -> Pod
```

Deployment giúp bạn:

- khai báo số replica mong muốn
- tự tạo lại Pod khi Pod chết
- rolling update khi đổi image hoặc config
- rollback về version trước
- giữ lịch sử rollout

### ReplicaSet là gì?

ReplicaSet đảm bảo luôn có đúng số Pod khớp với selector.

Ví dụ bạn muốn:

```text
replicas: 3
selector: app=order-service
```

Nếu chỉ còn 2 Pod có label `app=order-service`, ReplicaSet sẽ tạo thêm 1 Pod.

Thông thường bạn không tạo ReplicaSet trực tiếp. Bạn tạo Deployment, Deployment sẽ tạo và quản lý ReplicaSet.

### Tạo Deployment

Tạo file `order-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  labels:
    app: order-service
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
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
```

Apply:

```bash
kubectl apply -f order-deployment.yaml
```

Kiểm tra:

```bash
kubectl get deployments
kubectl get replicasets
kubectl get pods
kubectl get pods -l app=order-service
```

Xem chi tiết Deployment:

```bash
kubectl describe deployment order-service
```

### Failure Lab: xóa Pod

Xóa một Pod bất kỳ:

```bash
kubectl delete pod <pod-name>
```

Quan sát:

```bash
kubectl get pods -w
```

Bạn sẽ thấy Kubernetes tạo Pod mới để số replica quay lại 3.

Đây là self-healing ở mức cơ bản.

### Scale thủ công

Scale lên 5 Pod:

```bash
kubectl scale deployment order-service --replicas=5
kubectl get pods -l app=order-service
```

Scale về 3 Pod:

```bash
kubectl scale deployment order-service --replicas=3
```

### Rolling update cơ bản

Đổi image:

```bash
kubectl set image deployment/order-service order-service=nginx:1.27
```

Theo dõi rollout:

```bash
kubectl rollout status deployment/order-service
```

Xem lịch sử rollout:

```bash
kubectl rollout history deployment/order-service
```

Rollback:

```bash
kubectl rollout undo deployment/order-service
```

### Câu hỏi tự kiểm tra

- Deployment khác Pod trực tiếp ở điểm nào?
- ReplicaSet đảm bảo điều gì?
- Vì sao selector phải match với label trong Pod template?
- Khi xóa một Pod thuộc Deployment, vì sao Pod mới được tạo lại?

## Ngày 4: Labels, Selectors và Namespace

### Label là gì?

**Label** là key-value metadata dùng để phân loại và liên kết tài nguyên.

Ví dụ:

```yaml
metadata:
  labels:
    app: order-service
    component: backend
    environment: development
```

Label không chỉ để trang trí. Kubernetes dùng label cho rất nhiều cơ chế quan trọng:

- Deployment tìm Pod qua selector
- Service route traffic đến Pod qua selector
- `kubectl` filter resource
- policy, monitoring, logging phân nhóm workload

### Selector là gì?

**Selector** là điều kiện để chọn resource theo label.

Ví dụ Service này chọn các Pod có label `app=order-service`:

```yaml
selector:
  app: order-service
```

Nếu Pod không có label khớp, Service sẽ không route traffic đến Pod đó.

### Annotation là gì?

Annotation cũng là metadata, nhưng thường dùng để lưu thông tin phụ cho tool hoặc controller.

Khác nhau đơn giản:

- **Label**: dùng để chọn, lọc, liên kết resource
- **Annotation**: dùng để ghi chú hoặc cấu hình phụ, không dùng để select resource

Ví dụ annotation:

```yaml
metadata:
  annotations:
    description: "Order service for ecommerce system"
```

### Namespace là gì?

**Namespace** giúp chia cluster thành nhiều không gian logic.

Ví dụ:

- `development`
- `staging`
- `production`
- `ecommerce`

Tạo namespace:

```bash
kubectl create namespace ecommerce
```

Apply resource vào namespace:

```bash
kubectl apply -f order-deployment.yaml -n ecommerce
```

Liệt kê resource trong namespace:

```bash
kubectl get pods -n ecommerce
kubectl get deployments -n ecommerce
```

Đặt namespace mặc định cho context hiện tại:

```bash
kubectl config set-context --current --namespace=ecommerce
```

### Thực hành với label

Xem Pod theo label:

```bash
kubectl get pods -l app=order-service
```

Thêm label cho Deployment:

```bash
kubectl label deployment order-service component=backend
```

Xem label:

```bash
kubectl get deployments --show-labels
kubectl get pods --show-labels
```

### Câu hỏi tự kiểm tra

- Label khác annotation ở điểm nào?
- Service dùng selector để làm gì?
- Nếu selector của Deployment không match label trong Pod template thì chuyện gì xảy ra?
- Namespace có phải cơ chế bảo mật tuyệt đối không?

## Ngày 5: Service

### Vì sao cần Service?

Pod IP không ổn định. Khi Pod bị xóa và tạo lại, Pod mới thường có IP mới.

Nếu service khác gọi trực tiếp Pod IP, hệ thống sẽ rất dễ hỏng:

```text
Payment Service -> http://10.244.1.12:80
```

Khi Pod chết, IP này biến mất.

Kubernetes giải quyết bằng **Service**.

Service cung cấp:

- virtual IP ổn định
- DNS name ổn định
- load balancing đến nhiều Pod phía sau

Service khác trong cùng namespace có thể gọi:

```text
http://order-service
```

Không cần biết Pod nào đang chạy ở đâu.

### Các loại Service phổ biến

| Loại Service | Dùng khi nào? |
| --- | --- |
| ClusterIP | Expose service nội bộ trong cluster. Đây là loại mặc định. |
| NodePort | Mở port trên mỗi Node để truy cập từ ngoài cluster. Hay dùng cho học local, ít dùng trực tiếp trong production. |
| LoadBalancer | Tạo load balancer bên ngoài qua cloud provider. |
| ExternalName | Map service name trong cluster tới DNS name bên ngoài. |

Với backend service nội bộ, bạn thường bắt đầu bằng `ClusterIP`.

### Tạo ClusterIP Service

Tạo file `order-service.yaml`:

```yaml
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
```

Apply:

```bash
kubectl apply -f order-service.yaml
```

Kiểm tra:

```bash
kubectl get services
kubectl get service order-service
kubectl describe service order-service
```

Xem endpoints phía sau Service:

```bash
kubectl get endpoints order-service
```

Hoặc với Kubernetes mới hơn:

```bash
kubectl get endpointslices
```

### Test Service bằng port-forward

Forward Service ra máy local:

```bash
kubectl port-forward service/order-service 8080:80
```

Mở:

```text
http://localhost:8080
```

Bạn đang truy cập vào Service, không phải trực tiếp Pod.

### Failure Lab: Service vẫn sống khi Pod thay đổi

Scale Deployment:

```bash
kubectl scale deployment order-service --replicas=3
```

Xem Pod:

```bash
kubectl get pods -l app=order-service -o wide
```

Xóa một Pod:

```bash
kubectl delete pod <pod-name>
```

Kiểm tra lại:

```bash
kubectl get pods -l app=order-service -o wide
kubectl get endpoints order-service
```

Service vẫn giữ tên `order-service`, còn danh sách Pod phía sau được Kubernetes cập nhật.

### Câu hỏi tự kiểm tra

- Vì sao không nên gọi Pod IP trực tiếp?
- Service chọn Pod phía sau bằng gì?
- `port` và `targetPort` khác nhau thế nào?
- Khi Pod bị thay IP, vì sao client vẫn gọi được Service?

## Bài thực hành tổng hợp cuối tuần

Mục tiêu: deploy `Order Service` chạy 3 replica và expose bằng `ClusterIP Service`.

### 1. Tạo namespace

```bash
kubectl create namespace ecommerce
kubectl config set-context --current --namespace=ecommerce
```

### 2. Tạo Deployment

Tạo file `order-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  labels:
    app: order-service
    component: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
        component: backend
    spec:
      containers:
        - name: order-service
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
```

Apply:

```bash
kubectl apply -f order-deployment.yaml
```

### 3. Tạo Service

Tạo file `order-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: order-service
  labels:
    app: order-service
spec:
  type: ClusterIP
  selector:
    app: order-service
  ports:
    - name: http
      port: 80
      targetPort: 80
```

Apply:

```bash
kubectl apply -f order-service.yaml
```

### 4. Kiểm tra toàn bộ

```bash
kubectl get all
kubectl get pods -o wide
kubectl get endpoints order-service
kubectl describe deployment order-service
kubectl describe service order-service
```

### 5. Test từ máy local

```bash
kubectl port-forward service/order-service 8080:80
```

Mở:

```text
http://localhost:8080
```

### 6. Kiểm tra self-healing

Lấy tên Pod:

```bash
kubectl get pods -l app=order-service
```

Xóa một Pod:

```bash
kubectl delete pod <pod-name>
```

Quan sát:

```bash
kubectl get pods -w
```

Bạn cần thấy Pod mới được tạo lại để tổng số replica quay về 3.

## Cheatsheet Tuần 1

### Cluster và Node

```bash
kubectl cluster-info
kubectl get nodes
kubectl get nodes -o wide
```

### Pod

```bash
kubectl get pods
kubectl get pods -o wide
kubectl describe pod <pod-name>
kubectl logs <pod-name>
kubectl exec -it <pod-name> -- sh
```

### Deployment

```bash
kubectl get deployments
kubectl describe deployment <deployment-name>
kubectl scale deployment <deployment-name> --replicas=3
kubectl rollout status deployment/<deployment-name>
kubectl rollout history deployment/<deployment-name>
kubectl rollout undo deployment/<deployment-name>
```

### ReplicaSet

```bash
kubectl get replicasets
kubectl describe replicaset <replicaset-name>
```

### Service

```bash
kubectl get services
kubectl describe service <service-name>
kubectl get endpoints <service-name>
kubectl port-forward service/<service-name> 8080:80
```

### Label và Namespace

```bash
kubectl get pods --show-labels
kubectl get pods -l app=order-service
kubectl create namespace ecommerce
kubectl get pods -n ecommerce
kubectl config set-context --current --namespace=ecommerce
```

## Những lỗi hay gặp

### Service không route được vào Pod

Kiểm tra selector của Service:

```bash
kubectl describe service order-service
kubectl get pods --show-labels
```

Nếu Service selector là:

```yaml
selector:
  app: order-service
```

thì Pod phải có label:

```yaml
labels:
  app: order-service
```

### Pod ở trạng thái ImagePullBackOff

Nguyên nhân thường gặp:

- image name sai
- tag không tồn tại
- image private nhưng chưa cấu hình pull secret
- với kind, image local chưa được load vào cluster

Nếu dùng image local với kind:

```bash
kind load docker-image ecommerce/order-service:local --name ecommerce
```

### Pod ở trạng thái CrashLoopBackOff

Nghĩa là container chạy lên rồi crash nhiều lần.

Debug:

```bash
kubectl logs <pod-name>
kubectl describe pod <pod-name>
```

### Xóa Pod nhưng Pod tự quay lại

Đây không phải lỗi. Nếu Pod thuộc Deployment, ReplicaSet sẽ tạo Pod mới để giữ số replica mong muốn.

Muốn xóa hẳn workload, xóa Deployment:

```bash
kubectl delete deployment order-service
```

## Checklist kết thúc tuần

Bạn đã hoàn thành tuần 1 nếu có thể tự trả lời:

- Cluster khác Node như thế nào?
- Control Plane gồm những thành phần chính nào?
- API Server, Scheduler, kubelet làm nhiệm vụ gì?
- Pod là gì và vì sao Pod là ephemeral?
- Deployment, ReplicaSet, Pod liên hệ với nhau thế nào?
- Label và selector liên kết resource ra sao?
- Namespace dùng để làm gì?
- Service giải quyết vấn đề gì?
- Vì sao không nên gọi trực tiếp Pod IP?
- Làm sao debug Pod bằng `describe`, `logs`, `exec`?

Bạn cũng cần tự làm được:

```text
Tạo cluster kind
Tạo namespace ecommerce
Deploy order-service bằng Deployment
Scale order-service lên 3 Pod
Expose bằng ClusterIP Service
Port-forward để test
Xóa một Pod và quan sát Kubernetes tự tạo lại Pod mới
```

## Đáp Án Gợi Ý Cho Câu Hỏi Tự Kiểm Tra

### Ngày 1

- Kubernetes quản lý desired state bằng cách lưu trạng thái mong muốn qua API Server vào `etcd`, rồi các controller liên tục so sánh trạng thái thực tế với trạng thái mong muốn. Nếu có lệch, controller tạo/cập nhật/xóa resource để kéo cluster về đúng trạng thái.
- API Server là cổng giao tiếp trung tâm của cluster. `kubectl`, controller, scheduler và nhiều component khác đều nói chuyện với API Server.
- Scheduler chọn Node phù hợp cho Pod mới. Kubelet chạy trên từng Node và đảm bảo container của Pod được chạy đúng trên Node đó.
- Container runtime không phải Kubernetes. Nó là thành phần chạy container thật sự, ví dụ `containerd` hoặc CRI-O.

### Ngày 2

- Pod là tài nguyên tạm thời vì nó có thể bị xóa, restart, thay IP hoặc được tạo lại trên Node khác. Bạn không nên xem Pod như một server cố định.
- Không nên gọi Pod IP trực tiếp vì Pod IP không ổn định. Client nên gọi qua Service để có DNS và virtual IP ổn định.
- Một Pod có thể có nhiều container. Các container trong cùng Pod chia sẻ network namespace và có thể gọi nhau qua `localhost`.
- Pod tạo trực tiếp không tự quay lại sau khi bị xóa vì không có controller như Deployment/ReplicaSet đứng phía sau để duy trì desired state.

### Ngày 3

- Deployment khác Pod trực tiếp ở chỗ Deployment quản lý vòng đời Pod thông qua ReplicaSet, có self-healing, scale, rolling update và rollback.
- ReplicaSet đảm bảo luôn có số Pod mong muốn khớp với selector.
- Selector phải match label trong Pod template vì ReplicaSet/Deployment dùng selector để biết Pod nào thuộc quyền quản lý của nó.
- Khi xóa một Pod thuộc Deployment, ReplicaSet thấy số Pod thực tế ít hơn desired state nên tạo Pod mới.

### Ngày 4

- Label dùng để chọn, lọc và liên kết resource. Annotation dùng để lưu metadata phụ cho tool/controller, không dùng làm selector.
- Service dùng selector để tìm các Pod phía sau và route traffic đến chúng.
- Nếu selector của Deployment không match label trong Pod template, Deployment không thể quản lý đúng Pod. Kubernetes thường chặn một số cấu hình selector/template không hợp lệ vì selector của Deployment là phần rất quan trọng.
- Namespace không phải cơ chế bảo mật tuyệt đối. Nó là cách chia tài nguyên theo không gian logic; bảo mật cần thêm RBAC, NetworkPolicy, quota và policy khác.

### Ngày 5

- Không nên gọi Pod IP trực tiếp vì Pod IP thay đổi khi Pod bị tạo lại. Service cung cấp tên DNS và virtual IP ổn định.
- Service chọn Pod phía sau bằng selector match với label của Pod.
- `port` là port mà Service expose. `targetPort` là port trên container/Pod mà Service forward traffic tới.
- Khi Pod bị thay IP, Kubernetes cập nhật endpoints/EndpointSlice của Service, nên client vẫn gọi DNS Service như cũ.
