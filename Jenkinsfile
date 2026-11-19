pipeline {
    agent any

    environment {
        DOCKERHUB_REPO  = "2025tm93063/aceest-fitness"
        IMAGE_TAG       = "${env.BUILD_NUMBER}"
        SONAR_PROJECT   = "aceest-fitness"
        DB_PATH         = "/tmp/aceest_test.db"
        PATH            = "/var/lib/jenkins/.local/bin:${env.PATH}"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                echo "Branch: ${env.GIT_BRANCH} | Commit: ${env.GIT_COMMIT?.take(8)}"
            }
        }

        stage('Install Dependencies') {
            steps {
                sh 'pip3 install --quiet -r requirements.txt'
            }
        }

        stage('Lint') {
            steps {
                sh 'flake8 app.py --max-line-length=120 --ignore=E501,W503'
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    DB_PATH=/tmp/aceest_test.db \
                    python3 -m pytest tests/ -v \
                        --junitxml=test-results.xml \
                        --cov=app \
                        --cov-report=xml:coverage.xml \
                        --cov-report=term-missing
                '''
            }
            post {
                always {
                    junit 'test-results.xml'
                }
            }
        }

        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('sonarqube') {
                    sh '''
                        sonar-scanner \
                            -Dsonar.projectKey=aceest-fitness \
                            -Dsonar.projectName=aceest-fitness \
                            -Dsonar.projectVersion=3.2.4 \
                            -Dsonar.sources=. \
                            -Dsonar.inclusions=app.py \
                            -Dsonar.exclusions=tests/**,**/*.xml \
                            -Dsonar.python.coverage.reportPaths=coverage.xml \
                            -Dsonar.python.xunit.reportPath=test-results.xml
                    '''
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh "docker build -t ${DOCKERHUB_REPO}:${IMAGE_TAG} -t ${DOCKERHUB_REPO}:latest ."
            }
        }

        stage('Docker Push') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh '''
                        echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
                        docker push ${DOCKERHUB_REPO}:${IMAGE_TAG}
                        docker push ${DOCKERHUB_REPO}:latest
                    '''
                }
            }
        }

        stage('Smoke Test') {
            steps {
                sh '''
                    docker stop aceest-smoke || true
                    docker rm aceest-smoke || true
                    docker run -d --name aceest-smoke \
                        -p 8082:5000 \
                        -e DB_PATH=/tmp/aceest.db \
                        ${DOCKERHUB_REPO}:${IMAGE_TAG}
                    sleep 5
                    curl -f http://localhost:8082/health || (docker logs aceest-smoke && exit 1)
                    docker stop aceest-smoke
                    docker rm aceest-smoke
                '''
            }
        }

        stage('Deploy to Staging (K8s Rolling Update)') {
            steps {
                sh '''
                    kubectl apply -f k8s/namespace.yaml
                    kubectl apply -f k8s/deployment.yaml
                    kubectl apply -f k8s/service.yaml
                    kubectl set image deployment/aceest-fitness \
                        aceest=${DOCKERHUB_REPO}:${IMAGE_TAG} \
                        -n aceest
                    kubectl rollout status deployment/aceest-fitness -n aceest --timeout=90s
                '''
            }
        }

    }

    post {
        success {
            echo "Pipeline SUCCESS — image ${DOCKERHUB_REPO}:${IMAGE_TAG} deployed to staging"
        }
        failure {
            echo "Pipeline FAILED — check logs above"
        }
        always {
            sh 'docker logout || true'
        }
    }
}
