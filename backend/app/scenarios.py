SCENARIOS = {
    "oomkilled": {
        "id": "oomkilled",
        "title": "Out Of Memory (OOMKilled) Crash Loop",
        "category": "Resource Constraint",
        "severity": "CRITICAL",
        "affected_component": "api-service",
        # Label value (app=<pod_label>) used to find the pods for telemetry.
        "pod_label": "api-service",
        "description": "The API deployment container triggers a memory stress test that exceeds allocated limits (64Mi limit vs 150Mi load), causing Linux Cgroups OOM Killer to terminate process exit code 137.",
        "problem_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
    spec:
      containers:
      - name: memory-stress
        image: polinux/stress
        command: ["stress"]
        args: ["--vm", "1", "--vm-bytes", "150M", "--vm-hang", "1"]
        resources:
          limits:
            memory: "64Mi"
          requests:
            memory: "32Mi"
""",
        "fix_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
    spec:
      containers:
      - name: memory-stress
        image: polinux/stress
        command: ["stress"]
        args: ["--vm", "1", "--vm-bytes", "150M", "--vm-hang", "1"]
        resources:
          limits:
            memory: "256Mi"
          requests:
            memory: "128Mi"
"""
    },
    "crashloop": {
        "id": "crashloop",
        "title": "Missing Secret Environment Dependency",
        "category": "Configuration Error",
        "severity": "HIGH",
        "affected_component": "auth-service",
        "pod_label": "auth-service",
        "description": "Auth service cannot start because it references a Kubernetes Secret ('missing-db-secret') that does not exist in the namespace. Kubernetes keeps the pod in CreateContainerConfigError: the container is never created, so there are no application logs, only events.",
        "problem_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-api
        image: busybox
        command: ['sh', '-c', 'if [ -z "$DB_PASSWORD" ]; then echo "Fatal: DB_PASSWORD env var missing!"; exit 1; fi; sleep 3600']
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: missing-db-secret
              key: password
""",
        "fix_yaml": """apiVersion: v1
kind: Secret
metadata:
  name: missing-db-secret
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
type: Opaque
stringData:
  password: "demo-placeholder-not-a-real-secret"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-api
        image: busybox
        command: ['sh', '-c', 'if [ -z "$DB_PASSWORD" ]; then echo "Fatal: DB_PASSWORD env var missing!"; exit 1; fi; sleep 3600']
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: missing-db-secret
              key: password
"""
    },
    "broken_routing": {
        "id": "broken_routing",
        "title": "Service Label Selector Mismatch",
        "category": "Networking",
        "severity": "MEDIUM",
        "affected_component": "payment-service",
        # The Deployment's pods are labeled app=payment-processor, not payment-service.
        "pod_label": "payment-processor",
        # The problem is visible on the Service (no endpoints), not in pod logs.
        "service_name": "payment-service",
        "description": "Payment service Pods are running and healthy, but the Service selector points to 'app: wrong-label-selector', leaving the Endpoints object empty (<none>).",
        "problem_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-backend
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: payment-processor
  template:
    metadata:
      labels:
        app: payment-processor
    spec:
      containers:
      - name: payment
        image: nginx:alpine
---
apiVersion: v1
kind: Service
metadata:
  name: payment-service
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 80
  selector:
    app: wrong-label-selector
""",
        "fix_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-backend
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: payment-processor
  template:
    metadata:
      labels:
        app: payment-processor
    spec:
      containers:
      - name: payment
        image: nginx:alpine
---
apiVersion: v1
kind: Service
metadata:
  name: payment-service
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 80
  selector:
    app: payment-processor
"""
    },
    "memory_leak": {
        "id": "memory_leak",
        "title": "Memory Leak (Growing Memory Usage)",
        "category": "Resource Constraint",
        "severity": "HIGH",
        "affected_component": "cache-service",
        "pod_label": "cache-service",
        "description": "The cache service keeps allocating memory (about 700Mi) while its container limit is 512Mi. Two replicas fill their limit, are OOMKilled and restart in a loop, so cluster memory usage visibly climbs and drops. Bounded by design: at most 2 pods x 512Mi.",
        "problem_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: cache-service
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cache-service
  template:
    metadata:
      labels:
        app: cache-service
    spec:
      containers:
      - name: leaky-cache
        image: polinux/stress
        command: ["stress"]
        args: ["--vm", "1", "--vm-bytes", "700M", "--vm-keep"]
        resources:
          limits:
            memory: "512Mi"
          requests:
            memory: "256Mi"
""",
        "fix_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: cache-service
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cache-service
  template:
    metadata:
      labels:
        app: cache-service
    spec:
      containers:
      - name: leaky-cache
        image: polinux/stress
        command: ["stress"]
        args: ["--vm", "1", "--vm-bytes", "200M", "--vm-keep"]
        resources:
          limits:
            memory: "512Mi"
          requests:
            memory: "256Mi"
"""
    },
    "cpu_saturation": {
        "id": "cpu_saturation",
        "title": "CPU Saturation (Runaway Workers)",
        "category": "Resource Constraint",
        "severity": "HIGH",
        "affected_component": "report-worker",
        "pod_label": "report-worker",
        "description": "Report workers spin in a busy loop. Two replicas run at their CPU limit (800m each), so cluster CPU usage visibly climbs and the pods are throttled. Bounded by design: at most 2 pods x 800m of the cluster's CPU.",
        "problem_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: report-worker
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: report-worker
  template:
    metadata:
      labels:
        app: report-worker
    spec:
      containers:
      - name: worker
        image: polinux/stress
        command: ["stress"]
        args: ["--cpu", "1"]
        resources:
          limits:
            cpu: "800m"
            memory: "64Mi"
          requests:
            cpu: "100m"
            memory: "32Mi"
""",
        "fix_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: report-worker
  labels:
    app.kubernetes.io/part-of: incident-simulator
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: report-worker
  template:
    metadata:
      labels:
        app: report-worker
    spec:
      containers:
      - name: worker
        image: polinux/stress
        command: ["stress"]
        args: ["--cpu", "1"]
        resources:
          limits:
            cpu: "200m"
            memory: "64Mi"
          requests:
            cpu: "100m"
            memory: "32Mi"
"""
    }
}
