pipeline {
  agent any

  options {
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timestamps()
  }

  parameters {
    string(name: 'REGISTRY', defaultValue: '192.168.10.210', description: 'Harbor registry host')
    string(name: 'REPOSITORY', defaultValue: 'local-ai', description: 'Harbor project or repository namespace')
    string(name: 'IMAGE_TAG', defaultValue: '', description: 'Image tag. Empty uses the Git commit SHA')
    string(name: 'STORAGE_CLASS', defaultValue: 'nfs-client', description: 'RWX StorageClass for package artifacts')
    string(name: 'KUBECONFIG_PATH', defaultValue: '/opt/jenkins/kube/config', description: 'Kubeconfig path on the Jenkins node')
    string(name: 'BUILD_PROXY_URL', defaultValue: '', description: 'Optional HTTP/HTTPS proxy used only during Docker image builds')
    string(name: 'BUILD_NO_PROXY_LIST', defaultValue: '127.0.0.1,localhost,192.168.10.0/24,192.168.10.210,192.168.10.211,192.168.10.220,.svc,.cluster.local', description: 'Optional no_proxy list passed to Docker image builds')
    string(name: 'BUILD_APT_MIRROR', defaultValue: 'https://mirrors.aliyun.com/debian', description: 'Debian apt mirror used during backend and worker image builds. Empty keeps Docker image defaults.')
    string(name: 'BUILD_APT_SECURITY_MIRROR', defaultValue: 'https://mirrors.aliyun.com/debian-security', description: 'Debian security apt mirror used during backend and worker image builds. Empty keeps Docker image defaults.')
    string(name: 'BUILD_NPM_REGISTRY', defaultValue: 'https://registry.npmmirror.com', description: 'npm registry used during frontend image builds. Empty keeps npm defaults.')
    booleanParam(name: 'PUSH_IMAGES', defaultValue: true, description: 'Push backend, worker, and frontend images to Harbor')
    booleanParam(name: 'DEPLOY_TO_K8S', defaultValue: true, description: 'Apply deploy/generated to Kubernetes')
    booleanParam(name: 'USE_IN_CLUSTER_POSTGRES', defaultValue: true, description: 'Use the test namespace Postgres. Production should use an external database URL.')
    booleanParam(name: 'NO_CACHE', defaultValue: false, description: 'Build Docker images with --no-cache')
  }

  environment {
    NAMESPACE = 'deployment-package-factory'
    POSTGRES_IMAGE = '192.168.10.210/local-ai/postgres:16-alpine'
    DPF_API_TOKEN = credentials('dpf-api-token')
    DPF_DATABASE_URL = credentials('dpf-database-url')
  }

  stages {
    stage('Prepare') {
      steps {
        script {
          env.EFFECTIVE_IMAGE_TAG = params.IMAGE_TAG?.trim()
          if (!env.EFFECTIVE_IMAGE_TAG) {
            env.EFFECTIVE_IMAGE_TAG = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
          }
        }
        sh '''
          set -eux
          git rev-parse --short HEAD
          docker version
          kubectl --kubeconfig "${KUBECONFIG_PATH}" version --client=true
        '''
      }
    }

    stage('Build Images') {
      steps {
        sh '''
          set -eux
          cache_arg=""
          if [ "${NO_CACHE}" = "true" ]; then cache_arg="--no-cache"; fi
          export BUILD_PROXY_URL="${BUILD_PROXY_URL:-}"
          export BUILD_NO_PROXY_LIST="${BUILD_NO_PROXY_LIST:-}"
          export BUILD_APT_MIRROR="${BUILD_APT_MIRROR:-}"
          export BUILD_APT_SECURITY_MIRROR="${BUILD_APT_SECURITY_MIRROR:-}"
          export BUILD_NPM_REGISTRY="${BUILD_NPM_REGISTRY:-}"
          bash scripts/build-images.sh --registry "${REGISTRY}" --repository "${REPOSITORY}" --tag "${EFFECTIVE_IMAGE_TAG}" ${cache_arg}
        '''
      }
    }

    stage('Push Images') {
      when {
        expression { return params.PUSH_IMAGES }
      }
      steps {
        withCredentials([usernamePassword(credentialsId: 'harbor-admin', usernameVariable: 'REGISTRY_USERNAME', passwordVariable: 'REGISTRY_PASSWORD')]) {
          sh '''
            set -eux
            printf '%s' "${REGISTRY_PASSWORD}" | docker login "${REGISTRY}" --username "${REGISTRY_USERNAME}" --password-stdin
            bash scripts/push-images.sh --registry "${REGISTRY}" --repository "${REPOSITORY}" --tag "${EFFECTIVE_IMAGE_TAG}"
            docker logout "${REGISTRY}" || true
          '''
        }
      }
    }

    stage('Render Deploy Config') {
      steps {
        sh '''
          set -eux
          bash scripts/render-deploy-images.sh \
            --registry "${REGISTRY}" \
            --repository "${REPOSITORY}" \
            --tag "${EFFECTIVE_IMAGE_TAG}" \
            --http-port "5186" \
            --database-url "${DPF_DATABASE_URL}" \
            --storage-class "${STORAGE_CLASS}"
          bash scripts/render-k8s-secret.sh \
            --api-token "${DPF_API_TOKEN}" \
            --frontend-api-token "${DPF_API_TOKEN}" \
            --database-url "${DPF_DATABASE_URL}"
          bash scripts/validate-deploy-config.sh k8s
          kubectl --kubeconfig "${KUBECONFIG_PATH}" kustomize deploy/generated >/tmp/deployment-package-factory-rendered.yaml
        '''
      }
    }

    stage('Ensure Test Namespace') {
      when {
        expression { return params.DEPLOY_TO_K8S }
      }
      steps {
        withCredentials([usernamePassword(credentialsId: 'harbor-admin', usernameVariable: 'REGISTRY_USERNAME', passwordVariable: 'REGISTRY_PASSWORD')]) {
          sh '''
            set -eux
            export KUBECONFIG="${KUBECONFIG_PATH}"
            kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
            kubectl -n "${NAMESPACE}" create secret docker-registry harbor-pull-secret \
              --docker-server="${REGISTRY}" \
              --docker-username="${REGISTRY_USERNAME}" \
              --docker-password="${REGISTRY_PASSWORD}" \
              --dry-run=client -o yaml | kubectl apply -f -
          '''
        }
      }
    }

    stage('Ensure Test Postgres') {
      when {
        expression { return params.DEPLOY_TO_K8S && params.USE_IN_CLUSTER_POSTGRES }
      }
      steps {
        sh '''
          set -eux
          export KUBECONFIG="${KUBECONFIG_PATH}"
          cat >/tmp/deployment-package-factory-postgres.yaml <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: deployment-package-factory-postgres
  namespace: ${NAMESPACE}
type: Opaque
stringData:
  POSTGRES_DB: deployment_package_factory
  POSTGRES_USER: factory
  POSTGRES_PASSWORD: factory
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deployment-package-factory-postgres
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: deployment-package-factory
      app.kubernetes.io/component: postgres
  template:
    metadata:
      labels:
        app.kubernetes.io/name: deployment-package-factory
        app.kubernetes.io/component: postgres
    spec:
      imagePullSecrets:
        - name: harbor-pull-secret
      containers:
        - name: postgres
          image: ${POSTGRES_IMAGE}
          ports:
            - containerPort: 5432
          envFrom:
            - secretRef:
                name: deployment-package-factory-postgres
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "factory", "-d", "deployment_package_factory"]
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: deployment-package-factory-postgres
  namespace: ${NAMESPACE}
spec:
  selector:
    app.kubernetes.io/name: deployment-package-factory
    app.kubernetes.io/component: postgres
  ports:
    - name: postgres
      port: 5432
      targetPort: 5432
EOF
          kubectl apply -f /tmp/deployment-package-factory-postgres.yaml
          kubectl rollout status deployment/deployment-package-factory-postgres -n "${NAMESPACE}" --timeout=180s
        '''
      }
    }

    stage('Deploy to K8s') {
      when {
        expression { return params.DEPLOY_TO_K8S }
      }
      steps {
        sh '''
          set -eux
          export KUBECONFIG="${KUBECONFIG_PATH}"
          kubectl apply -k deploy/generated
          kubectl -n "${NAMESPACE}" patch serviceaccount deployment-package-factory -p '{"imagePullSecrets":[{"name":"harbor-pull-secret"}]}' || true
          kubectl -n "${NAMESPACE}" patch serviceaccount default -p '{"imagePullSecrets":[{"name":"harbor-pull-secret"}]}' || true
          kubectl rollout status deployment/deployment-package-factory-backend -n "${NAMESPACE}" --timeout=240s
          kubectl rollout status deployment/deployment-package-factory-worker -n "${NAMESPACE}" --timeout=240s
          kubectl rollout status deployment/deployment-package-factory-frontend -n "${NAMESPACE}" --timeout=240s
          kubectl get pods -n "${NAMESPACE}" -o wide
        '''
      }
    }

    stage('Smoke Test') {
      when {
        expression { return params.DEPLOY_TO_K8S }
      }
      steps {
        sh '''
          set -eux
          export KUBECONFIG="${KUBECONFIG_PATH}"
          kubectl -n "${NAMESPACE}" wait --for=condition=Ready pod -l app.kubernetes.io/component=backend --timeout=120s
          POD=$(kubectl -n "${NAMESPACE}" get pod -l app.kubernetes.io/component=backend \
            --field-selector=status.phase=Running \
            -o jsonpath='{.items[?(@.status.containerStatuses[0].ready==true)].metadata.name}' | awk '{print $1}')
          test -n "$POD"
          kubectl -n "${NAMESPACE}" exec "$POD" -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8096/health', timeout=20).read().decode())"
          kubectl -n "${NAMESPACE}" exec "$POD" -- python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8096/metrics', timeout=20); print(r.status); print(r.read().decode()[:300])"
          kubectl -n "${NAMESPACE}" exec "$POD" -- python -c "import urllib.request; req=urllib.request.Request('http://127.0.0.1:8096/api/deployment-packages/options', headers={'Authorization':'Bearer ${DPF_API_TOKEN}'}); r=urllib.request.urlopen(req, timeout=20); print(r.status); print(r.read().decode()[:300])"
        '''
      }
    }
  }

  post {
    always {
      sh '''
        set +e
        rm -f deploy/generated/factory.env deploy/k8s/secret.yaml /tmp/deployment-package-factory-rendered.yaml
      '''
      archiveArtifacts artifacts: 'deploy/generated/kustomization.yaml,deploy/generated/pvc-storage-class-patch.yaml', allowEmptyArchive: true, fingerprint: true
    }
  }
}
