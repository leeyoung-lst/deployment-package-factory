pipeline {
  agent any

  options {
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  parameters {
    string(name: 'REGISTRY', defaultValue: 'registry.example.com', description: 'Container registry host, for example harbor.example.com')
    string(name: 'REPOSITORY', defaultValue: 'platform', description: 'Registry repository or namespace')
    string(name: 'IMAGE_TAG', defaultValue: '', description: 'Image tag. Empty uses branch-buildNumber')
    string(name: 'STORAGE_CLASS', defaultValue: 'nfs-rwx', description: 'RWX StorageClass for package artifacts')
    string(name: 'HTTP_PORT', defaultValue: '5186', description: 'Frontend service host port used by generated compose env')
    booleanParam(name: 'PUSH_IMAGES', defaultValue: true, description: 'Push backend, worker, and frontend images to REGISTRY')
    booleanParam(name: 'DEPLOY_TO_K8S', defaultValue: false, description: 'Apply deploy/generated to Kubernetes')
    booleanParam(name: 'NO_CACHE', defaultValue: false, description: 'Build Docker images with --no-cache')
  }

  environment {
    PYTHONUNBUFFERED = '1'
    DEPLOYMENT_PACKAGE_TEMPLATE_DIR = "${WORKSPACE}/templates"
  }

  stages {
    stage('Prepare') {
      steps {
        script {
          env.EFFECTIVE_IMAGE_TAG = params.IMAGE_TAG?.trim()
          if (!env.EFFECTIVE_IMAGE_TAG) {
            env.EFFECTIVE_IMAGE_TAG = "${env.BRANCH_NAME ?: 'local'}-${env.BUILD_NUMBER}".replaceAll('[^A-Za-z0-9_.-]', '-')
          }
        }
        sh '''
          set -eux
          python --version
          node --version
          corepack --version || true
          docker version
          kubectl version --client=true
        '''
      }
    }

    stage('Backend Tests') {
      steps {
        sh 'python -m pytest backend/tests -q'
      }
    }

    stage('Frontend Build') {
      steps {
        sh '''
          set -eux
          corepack enable
          corepack prepare pnpm@10.24.0 --activate
          pnpm --dir frontend install --frozen-lockfile
          pnpm --dir frontend build
        '''
      }
    }

    stage('Validate Manifests') {
      steps {
        sh '''
          set -eux
          python -c "from pathlib import Path; import yaml; [list(yaml.safe_load_all(p.read_text(encoding='utf-8'))) for p in Path('deploy/k8s').glob('*.yaml')]; print('yaml ok')"
          git diff --check
        '''
      }
    }

    stage('Build Images') {
      steps {
        script {
          def cacheArg = params.NO_CACHE ? ' --no-cache' : ''
          sh "bash scripts/build-images.sh --registry '${params.REGISTRY}' --repository '${params.REPOSITORY}' --tag '${env.EFFECTIVE_IMAGE_TAG}'${cacheArg}"
        }
      }
    }

    stage('Push Images') {
      when {
        expression { return params.PUSH_IMAGES }
      }
      steps {
        withCredentials([usernamePassword(credentialsId: 'dpf-registry-credentials', usernameVariable: 'REGISTRY_USERNAME', passwordVariable: 'REGISTRY_PASSWORD')]) {
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
        withCredentials([
          string(credentialsId: 'dpf-api-token', variable: 'DPF_API_TOKEN'),
          string(credentialsId: 'dpf-database-url', variable: 'DPF_DATABASE_URL')
        ]) {
          sh '''
            set -eux
            bash scripts/render-deploy-images.sh \
              --registry "${REGISTRY}" \
              --repository "${REPOSITORY}" \
              --tag "${EFFECTIVE_IMAGE_TAG}" \
              --http-port "${HTTP_PORT}" \
              --database-url "${DPF_DATABASE_URL}" \
              --storage-class "${STORAGE_CLASS}"
            bash scripts/render-k8s-secret.sh \
              --api-token "${DPF_API_TOKEN}" \
              --frontend-api-token "${DPF_API_TOKEN}" \
              --database-url "${DPF_DATABASE_URL}"
            bash scripts/validate-deploy-config.sh k8s
            kubectl kustomize deploy/generated >/tmp/deployment-package-factory-rendered.yaml
          '''
        }
      }
    }

    stage('Deploy to K8s') {
      when {
        expression { return params.DEPLOY_TO_K8S }
      }
      steps {
        withCredentials([file(credentialsId: 'dpf-kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          sh '''
            set -eux
            export KUBECONFIG="${KUBECONFIG_FILE}"
            kubectl apply -k deploy/generated
            kubectl rollout status deployment/deployment-package-factory-backend -n deployment-package-factory --timeout=180s
            kubectl rollout status deployment/deployment-package-factory-worker -n deployment-package-factory --timeout=180s
            kubectl rollout status deployment/deployment-package-factory-frontend -n deployment-package-factory --timeout=180s
            kubectl get pods -n deployment-package-factory
          '''
        }
      }
    }
  }

  post {
    always {
      sh 'rm -f deploy/generated/factory.env deploy/k8s/secret.yaml /tmp/deployment-package-factory-rendered.yaml || true'
      archiveArtifacts artifacts: 'deploy/generated/kustomization.yaml,deploy/generated/pvc-storage-class-patch.yaml', allowEmptyArchive: true, fingerprint: true
    }
  }
}
