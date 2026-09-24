SCENARIOS = {
    "oomkilled": {
        "id": "oomkilled",
        "title": "Out Of Memory (OOMKilled) Crash Loop",
        "category": "Resource Constraint",
        "severity": "CRITICAL",
        "affected_component": "api-service",
        "description": "The API deployment container triggers a memory stress test that exceeds allocated limits (64Mi limit vs 150Mi load), causing Linux Cgroups OOM Killer to terminate process exit code 137.",
        "problem_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
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
        "description": "Auth service fails startup initialization because it references a Kubernetes Secret ('missing-db-secret') that does not exist in the cluster namespace.",
        "problem_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
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
  namespace: default
type: Opaque
stringData:
  password: "SuperSecretPassword123!"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
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
        "description": "Payment service Pods are running and healthy, but the Service selector points to 'app: wrong-label-selector', leaving the Endpoints object empty (<none>).",
        "problem_yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-backend
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
  namespace: default
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 80
  selector:
    app: payment-processor
"""
    }
}