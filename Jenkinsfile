pipeline {
    agent any

    environment {
        DOCKERHUB_REPO  = "YOUR_DOCKERHUB_USERNAME/aceest-fitness"
        IMAGE_TAG       = "${env.BUILD_NUMBER}"
        SONAR_PROJECT   = "aceest-fitness"
        DB_PATH         = "/tmp/aceest_test.db"
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
                dir('aceest-devops-a2') {
                    sh 'pip3 install --quiet -r requirements.txt'
                }
            }
        }

        stage('Lint') {
            steps {
                dir('aceest-devops-a2') {
                    sh 'flake8 app.py --max-line-length=120 --ignore=E501,W503'
                }
            }
        }

        stage('Run Tests') {
            steps {
                dir('aceest-devops-a2') {
                    sh '''
                        DB_PATH=/tmp/aceest_test.db \
                        pytest tests/ -v \
                            --junitxml=test-results.xml \
                            --cov=app \
                            --cov-report=xml:coverage.xml \
                            --cov-report=term-missing
                    '''
                }
            }
            post {
                always {
                    junit 'aceest-devops-a2/test-results.xml'
                }
            }
        }

        stage('SonarQube Analysis') {
            steps {
                dir('aceest-devops-a2') {
                    withSonarQubeEnv('SonarQube') {
                        sh '''
                            sonar-scanner \
                              -Dsonar.projectKey=${SONAR_PROJECT} \
                              -Dsonar.projectName="ACEest Fitness A2" \
                              -Dsonar.projectVersion=${IMAGE_TAG} \
                              -Dsonar.sources=. \
                              -Dsonar.exclusions=tests/**,**/__pycache__/** \
                              -Dsonar.python.coverage.reportPaths=coverage.xml \
                              -Dsonar.python.version=3.11
                        '''
                    }
                }
            }
        }

        stage('Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Docker Build') {
            steps {
                dir('aceest-devops-a2') {
                    sh "docker build -t ${DOCKERHUB_REPO}:${IMAGE_TAG} -t ${DOCKERHUB_REPO}:latest ."
                }
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
                dir('aceest-devops-a2') {
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
