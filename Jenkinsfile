pipeline {

    agent any

    parameters {
        booleanParam(
            name: 'BUILD_ALL',
            defaultValue: false,
            description: 'Build and deploy all services regardless of changes'
        )
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(
            numToKeepStr: '20',
            artifactNumToKeepStr: '10'
        ))
    }

    environment {
        REGISTRY   = "registry-vs.m-society.go.th"
        PROJECT    = "kitsune-cop"
        REPO       = "vcare-backend"
        BASE_IMAGE = "registry-vs.m-society.go.th/kitsune-cop/vcare-backend"
        IMAGE_TAG  = "${env.GIT_COMMIT?.take(8) ?: env.BUILD_NUMBER}"
        NAMESPACE  = "vcare"
        KUBECONFIG = "/var/lib/jenkins/.kube/config"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Images') {
            parallel {
                stage('bff') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "bff-vsmartcare/**"
                        }
                    }
                    steps {
                        sh '''
                            docker build \
                                -t ${BASE_IMAGE}:vcare-bff-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-bff-latest \
                                bff-vsmartcare/
                        '''
                    }
                }
                stage('case-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "case-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker build \
                                -t ${BASE_IMAGE}:vcare-case-service-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-case-service-latest \
                                case-service/
                        '''
                    }
                }
                stage('notification-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "notification-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker build \
                                -t ${BASE_IMAGE}:vcare-notification-service-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-notification-service-latest \
                                notification-service/
                        '''
                    }
                }
                stage('ocr-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "ocr-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker build \
                                -t ${BASE_IMAGE}:vcare-ocr-service-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-ocr-service-latest \
                                ocr-service/
                        '''
                    }
                }
                stage('thaid-auth-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "thaid-auth-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker build \
                                -t ${BASE_IMAGE}:vcare-thaid-auth-service-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-thaid-auth-service-latest \
                                thaid-auth-service/
                        '''
                    }
                }
                stage('dashboard-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "dashboard-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker build \
                                -t ${BASE_IMAGE}:vcare-dashboard-service-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-dashboard-service-latest \
                                dashboard-service/
                        '''
                    }
                }
            }
        }

        stage('Login Registry') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'devop-bot',
                        usernameVariable: 'REGISTRY_USER',
                        passwordVariable: 'REGISTRY_PASS'
                    )
                ]) {
                    sh '''
                        echo "$REGISTRY_PASS" | docker login ${REGISTRY} \
                            -u "$REGISTRY_USER" \
                            --password-stdin
                    '''
                }
            }
        }

        stage('Push Images') {
            parallel {
                stage('bff') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "bff-vsmartcare/**"
                        }
                    }
                    steps {
                        sh '''
                            docker push ${BASE_IMAGE}:vcare-bff-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-bff-latest
                        '''
                    }
                }
                stage('case-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "case-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker push ${BASE_IMAGE}:vcare-case-service-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-case-service-latest
                        '''
                    }
                }
                stage('notification-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "notification-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker push ${BASE_IMAGE}:vcare-notification-service-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-notification-service-latest
                        '''
                    }
                }
                stage('ocr-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "ocr-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker push ${BASE_IMAGE}:vcare-ocr-service-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-ocr-service-latest
                        '''
                    }
                }
                stage('thaid-auth-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "thaid-auth-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker push ${BASE_IMAGE}:vcare-thaid-auth-service-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-thaid-auth-service-latest
                        '''
                    }
                }
                stage('dashboard-service') {
                    when {
                        anyOf {
                            expression { return params.BUILD_ALL }
                            changeset "dashboard-service/**"
                        }
                    }
                    steps {
                        sh '''
                            docker push ${BASE_IMAGE}:vcare-dashboard-service-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-dashboard-service-latest
                        '''
                    }
                }
            }
        }

        stage('Deploy Kubernetes') {
            stages {
                stage('Apply Manifests') {
                    steps {
                        sh '''
                            export KUBECONFIG=${KUBECONFIG}
                            kubectl apply -f k8s/external-db.yml
                            kubectl apply -f k8s/case-service-storage.yml
                            kubectl apply -f k8s/deployment.yml
                            kubectl apply -f k8s/service.yml
                            kubectl apply -f k8s/hpa.yml
                        '''
                    }
                }
                stage('Rollout') {
                    parallel {
                        stage('bff') {
                            when {
                                anyOf {
                                    expression { return params.BUILD_ALL }
                                    changeset "bff-vsmartcare/**"
                                }
                            }
                            steps {
                                sh '''
                                    export KUBECONFIG=${KUBECONFIG}
                                    kubectl -n ${NAMESPACE} set image deployment/vcare-bff \
                                        vcare-bff=${BASE_IMAGE}:vcare-bff-${IMAGE_TAG}
                                    kubectl -n ${NAMESPACE} rollout status deployment/vcare-bff --timeout=300s
                                '''
                            }
                        }
                        stage('case-service') {
                            when {
                                anyOf {
                                    expression { return params.BUILD_ALL }
                                    changeset "case-service/**"
                                }
                            }
                            steps {
                                sh '''
                                    export KUBECONFIG=${KUBECONFIG}
                                    kubectl -n ${NAMESPACE} set image deployment/vcare-case-service \
                                        vcare-case-service=${BASE_IMAGE}:vcare-case-service-${IMAGE_TAG}
                                    kubectl -n ${NAMESPACE} rollout status deployment/vcare-case-service --timeout=300s
                                '''
                            }
                        }
                        stage('notification-service') {
                            when {
                                anyOf {
                                    expression { return params.BUILD_ALL }
                                    changeset "notification-service/**"
                                }
                            }
                            steps {
                                sh '''
                                    export KUBECONFIG=${KUBECONFIG}
                                    kubectl -n ${NAMESPACE} set image deployment/vcare-notification-service \
                                        vcare-notification-service=${BASE_IMAGE}:vcare-notification-service-${IMAGE_TAG}
                                    kubectl -n ${NAMESPACE} rollout status deployment/vcare-notification-service --timeout=300s
                                '''
                            }
                        }
                        stage('ocr-service') {
                            when {
                                anyOf {
                                    expression { return params.BUILD_ALL }
                                    changeset "ocr-service/**"
                                }
                            }
                            steps {
                                sh '''
                                    export KUBECONFIG=${KUBECONFIG}
                                    kubectl -n ${NAMESPACE} set image deployment/vcare-ocr-service \
                                        vcare-ocr-service=${BASE_IMAGE}:vcare-ocr-service-${IMAGE_TAG}
                                    kubectl -n ${NAMESPACE} rollout status deployment/vcare-ocr-service --timeout=300s
                                '''
                            }
                        }
                        stage('thaid-auth-service') {
                            when {
                                anyOf {
                                    expression { return params.BUILD_ALL }
                                    changeset "thaid-auth-service/**"
                                }
                            }
                            steps {
                                sh '''
                                    export KUBECONFIG=${KUBECONFIG}
                                    kubectl -n ${NAMESPACE} set image deployment/vcare-thaid-auth-service \
                                        vcare-thaid-auth-service=${BASE_IMAGE}:vcare-thaid-auth-service-${IMAGE_TAG}
                                    kubectl -n ${NAMESPACE} rollout status deployment/vcare-thaid-auth-service --timeout=300s
                                '''
                            }
                        }
                        stage('dashboard-service') {
                            when {
                                anyOf {
                                    expression { return params.BUILD_ALL }
                                    changeset "dashboard-service/**"
                                }
                            }
                            steps {
                                sh '''
                                    export KUBECONFIG=${KUBECONFIG}
                                    kubectl -n ${NAMESPACE} set image deployment/vcare-dashboard-service \
                                        vcare-dashboard-service=${BASE_IMAGE}:vcare-dashboard-service-${IMAGE_TAG}
                                    kubectl -n ${NAMESPACE} rollout status deployment/vcare-dashboard-service --timeout=300s
                                '''
                            }
                        }
                    }
                }
            }
        }

        stage('Verify') {
            steps {
                sh '''
                    export KUBECONFIG=${KUBECONFIG}

                    kubectl -n ${NAMESPACE} get deployment
                    kubectl -n ${NAMESPACE} get pods -o wide
                    kubectl -n ${NAMESPACE} get svc
                    kubectl -n ${NAMESPACE} get hpa
                '''
            }
        }
    }

    post {

        always {
            sh '''
                docker logout ${REGISTRY} || true
                docker image prune -f || true
            '''

            cleanWs()
        }

        success {
            echo "======================================"
            echo " Deploy Success"
            echo " Tag : ${IMAGE_TAG}"
            echo "======================================"
        }

        failure {
            echo "======================================"
            echo " Deploy Failed"
            echo " Tag : ${IMAGE_TAG}"
            echo "======================================"
        }
    }
}
