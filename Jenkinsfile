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
        // REGISTRY/BASE_IMAGE — using staging-registry-vs (root/vcare-backend) for
        // np too, on purpose, for now. np cannot actually pull from it until the
        // 2026-08-31 cutover (dev-np-quickstart.md item 38: the registry's
        // token-issuer realm still points at the OLD gitlab-vs host, so the JWT
        // exchange 401s from inside np). Until then, Push Images succeeds but
        // every np rollout below sits at ImagePullBackOff — expected, not a bug
        // here.
        //
        // WHAT TO CHANGE, AND WHEN: nothing, once the cutover lands —
        // REGISTRY/BASE_IMAGE already point at the correct long-term target, no
        // edit needed here. If you need np working BEFORE 2026-08-31, there is
        // no registry value that fixes it: our CI never pushes to the vendor
        // path np can currently pull from (registry-vs.m-society.go.th/kitsune-cop/*),
        // so pointing REGISTRY back there would just 404 on a nonexistent tag
        // instead of ImagePullBackOff. That path is only useful to confirm the
        // deploy mechanism itself (see ci/Jenkinsfile.np-smoke in the ops repo),
        // not to test a real build.
        REGISTRY   = "staging-registry-vs.m-society.go.th"
        PROJECT    = "root"
        REPO       = "vcare-backend"
        BASE_IMAGE = "staging-registry-vs.m-society.go.th/root/vcare-backend"
        IMAGE_TAG  = "${env.GIT_COMMIT?.take(8) ?: env.BUILD_NUMBER}"

        // beta pushes every image under a "-beta" suffixed tag so it never
        // overwrites production's :latest (and any other tag) on the shared
        // registry repo — used in Build/Push and in the beta Rollout branch below
        BRANCH_SUFFIX = "${(env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') ? '-beta' : ''}"

        // production-side cluster (172.21.103.x), ns vcare — used when NOT branch beta
        NAMESPACE  = "vcare"
        KUBECONFIG = "/var/lib/jenkins/.kube/config"

        // np/GDCC estate (192.168.10.x), ns staging — used only when branch beta.
        // See dev-np-quickstart.md §6.4 "Route C".
        NP_KUBECONFIG = "/var/lib/jenkins-agent/.kube/config"
        NP_NAMESPACE  = "staging"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Stash np Manifests') {
            // node('nonprod') below opens its own workspace on np-agent01
            // (/var/lib/jenkins-agent/workspace/...), separate from the one
            // Checkout just cloned into on the default agent — files aren't
            // shared between them automatically. Stash here once, unstash in
            // every node('nonprod') block that needs a k8s/*.yml file.
            when {
                expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
            }
            steps {
                stash name: 'np-manifests', includes: 'k8s/external-db-np.yml,k8s/case-service-storage-np.yml'
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
                                -t ${BASE_IMAGE}:vcare-bff${BRANCH_SUFFIX}-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-bff${BRANCH_SUFFIX}-latest \
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
                                -t ${BASE_IMAGE}:vcare-case-service${BRANCH_SUFFIX}-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-case-service${BRANCH_SUFFIX}-latest \
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
                                -t ${BASE_IMAGE}:vcare-notification-service${BRANCH_SUFFIX}-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-notification-service${BRANCH_SUFFIX}-latest \
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
                                -t ${BASE_IMAGE}:vcare-ocr-service${BRANCH_SUFFIX}-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-ocr-service${BRANCH_SUFFIX}-latest \
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
                                -t ${BASE_IMAGE}:vcare-thaid-auth-service${BRANCH_SUFFIX}-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-thaid-auth-service${BRANCH_SUFFIX}-latest \
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
                                -t ${BASE_IMAGE}:vcare-dashboard-service${BRANCH_SUFFIX}-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-dashboard-service${BRANCH_SUFFIX}-latest \
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
                            docker push ${BASE_IMAGE}:vcare-bff${BRANCH_SUFFIX}-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-bff${BRANCH_SUFFIX}-latest
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
                            docker push ${BASE_IMAGE}:vcare-case-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-case-service${BRANCH_SUFFIX}-latest
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
                            docker push ${BASE_IMAGE}:vcare-notification-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-notification-service${BRANCH_SUFFIX}-latest
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
                            docker push ${BASE_IMAGE}:vcare-ocr-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-ocr-service${BRANCH_SUFFIX}-latest
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
                            docker push ${BASE_IMAGE}:vcare-thaid-auth-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-thaid-auth-service${BRANCH_SUFFIX}-latest
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
                            docker push ${BASE_IMAGE}:vcare-dashboard-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                            docker push ${BASE_IMAGE}:vcare-dashboard-service${BRANCH_SUFFIX}-latest
                        '''
                    }
                }
            }
        }

        stage('Deploy Kubernetes') {
            stages {
                stage('Apply Manifests (prod only)') {
                    // np's Deployments/Services already exist on the cluster, created and
                    // managed by ops (see dev-np-quickstart.md) — beta never applies
                    // manifests here, it only updates images on the Rollout stage below.
                    when {
                        not { expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') } }
                    }
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
                stage('Ensure np External DB (beta only)') {
                    // Points ns staging at np-data01's real Postgres — see
                    // k8s/external-db-np.yml for why no proxy is needed here
                    // (unlike k8s/external-db.yml for ns vcare). Idempotent:
                    // safe to re-apply every beta run.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
                    }
                    steps {
                        node('nonprod') {
                            unstash 'np-manifests'
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} apply -f k8s/external-db-np.yml
                                '''
                            }
                        }
                    }
                }
                stage('Ensure np Case-Service Storage (beta only)') {
                    // Applies the PV/PVC that points case-service's uploads at the
                    // NFS export on np-store01 (192.168.10.22) — see
                    // k8s/case-service-storage-np.yml. Idempotent: safe to
                    // re-apply every beta run.
                    //
                    // This does NOT set up the NFS server itself or install
                    // nfs-common on the np worker nodes — both are one-time host
                    // prep done by hand (see the comments in that file); this
                    // stage only applies the k8s objects once those exist.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
                    }
                    steps {
                        node('nonprod') {
                            unstash 'np-manifests'
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} apply -f k8s/case-service-storage-np.yml

                                    if ! kubectl -n ${NP_NAMESPACE} wait --for=jsonpath='{.status.phase}'=Bound \
                                            pvc/vcare-case-service-uploads-beta-pvc --timeout=60s; then
                                        echo "--- PVC not Bound, describing ---"
                                        kubectl -n ${NP_NAMESPACE} describe pvc vcare-case-service-uploads-beta-pvc
                                        kubectl -n ${NP_NAMESPACE} describe pv vcare-case-service-uploads-np-pv
                                        exit 1
                                    fi

                                    kubectl -n ${NP_NAMESPACE} get pvc vcare-case-service-uploads-beta-pvc
                                '''
                            }
                        }
                    }
                }
                stage('Ensure np Pull Secret (beta only)') {
                    // Ensure "betabackcred" exists in ns staging and is wired into
                    // every service's Deployment before any rollout below tries to
                    // pull with it. Built from the same 'devop-bot' credential the
                    // Push Images stage already logs in with (server=REGISTRY), so
                    // there's no separate token to keep in sync by hand — every run
                    // refreshes it, which also self-heals if the credential is ever
                    // rotated. regcred/regcred-staging are kept alongside it rather
                    // than replaced: regcred is the only thing that can still pull
                    // the digest-pinned kitsune-cop images if a pod ever needs to
                    // fall back to them (dev-np-quickstart.md item 4), and the
                    // kubelet just tries each secret in turn.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
                    }
                    steps {
                        node('nonprod') {
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                withCredentials([
                                    usernamePassword(
                                        credentialsId: 'devop-bot',
                                        usernameVariable: 'REGISTRY_USER',
                                        passwordVariable: 'REGISTRY_PASS'
                                    )
                                ]) {
                                    sh '''
                                        kubectl -n ${NP_NAMESPACE} create secret docker-registry betabackcred \
                                            --docker-server=${REGISTRY} \
                                            --docker-username="$REGISTRY_USER" \
                                            --docker-password="$REGISTRY_PASS" \
                                            --dry-run=client -o yaml | kubectl apply -f -

                                        for d in bff-vsmartcare case-service notification-service \
                                                 ocr-service thaid-auth-service dashboard-service; do
                                            kubectl -n ${NP_NAMESPACE} patch deployment "$d" --type=json -p \
                                                '[{"op":"add","path":"/spec/template/spec/imagePullSecrets","value":[{"name":"regcred"},{"name":"regcred-staging"},{"name":"betabackcred"}]}]'
                                        done
                                    '''
                                }
                            }
                        }
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
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('beta')) {
                                        // np's Deployment for this service is "bff-vsmartcare",
                                        // not "vcare-bff" — see dev-np-quickstart.md §4. '*'
                                        // sidesteps needing the exact container name.
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/bff-vsmartcare \
                                                        '*'=${BASE_IMAGE}:vcare-bff${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/bff-vsmartcare --timeout=300s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/bff-vsmartcare
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=bff-vsmartcare
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else {
                                        sh '''
                                            export KUBECONFIG=${KUBECONFIG}
                                            kubectl -n ${NAMESPACE} set image deployment/vcare-bff \
                                                vcare-bff=${BASE_IMAGE}:vcare-bff-${IMAGE_TAG}
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-bff --timeout=300s
                                        '''
                                    }
                                }
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
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('beta')) {
                                        // case-service must stay at 1 replica on np — its
                                        // container runs the Alembic migration on start
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/case-service \
                                                        '*'=${BASE_IMAGE}:vcare-case-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/case-service --timeout=300s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/case-service
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=case-service
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else {
                                        sh '''
                                            export KUBECONFIG=${KUBECONFIG}
                                            kubectl -n ${NAMESPACE} set image deployment/vcare-case-service \
                                                vcare-case-service=${BASE_IMAGE}:vcare-case-service-${IMAGE_TAG}
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-case-service --timeout=300s
                                        '''
                                    }
                                }
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
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('beta')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/notification-service \
                                                        '*'=${BASE_IMAGE}:vcare-notification-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/notification-service --timeout=300s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/notification-service
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=notification-service
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else {
                                        sh '''
                                            export KUBECONFIG=${KUBECONFIG}
                                            kubectl -n ${NAMESPACE} set image deployment/vcare-notification-service \
                                                vcare-notification-service=${BASE_IMAGE}:vcare-notification-service-${IMAGE_TAG}
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-notification-service --timeout=300s
                                        '''
                                    }
                                }
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
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('beta')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/ocr-service \
                                                        '*'=${BASE_IMAGE}:vcare-ocr-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/ocr-service --timeout=300s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/ocr-service
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=ocr-service
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else {
                                        sh '''
                                            export KUBECONFIG=${KUBECONFIG}
                                            kubectl -n ${NAMESPACE} set image deployment/vcare-ocr-service \
                                                vcare-ocr-service=${BASE_IMAGE}:vcare-ocr-service-${IMAGE_TAG}
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-ocr-service --timeout=300s
                                        '''
                                    }
                                }
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
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('beta')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/thaid-auth-service \
                                                        '*'=${BASE_IMAGE}:vcare-thaid-auth-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/thaid-auth-service --timeout=300s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/thaid-auth-service
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=thaid-auth-service
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else {
                                        sh '''
                                            export KUBECONFIG=${KUBECONFIG}
                                            kubectl -n ${NAMESPACE} set image deployment/vcare-thaid-auth-service \
                                                vcare-thaid-auth-service=${BASE_IMAGE}:vcare-thaid-auth-service-${IMAGE_TAG}
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-thaid-auth-service --timeout=300s
                                        '''
                                    }
                                }
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
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('beta')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/dashboard-service \
                                                        '*'=${BASE_IMAGE}:vcare-dashboard-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/dashboard-service --timeout=300s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/dashboard-service
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=dashboard-service
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else {
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
            }
        }

        stage('Verify') {
            steps {
                script {
                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                    if (branchName.contains('beta')) {
                        node('nonprod') {
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} get deployment \
                                        bff-vsmartcare case-service notification-service \
                                        ocr-service thaid-auth-service dashboard-service
                                    kubectl -n ${NP_NAMESPACE} get pods -o wide
                                '''
                            }
                        }
                    } else {
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
