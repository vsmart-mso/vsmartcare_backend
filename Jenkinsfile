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
        // REGISTRY/BASE_IMAGE — "registry-vs" (no "staging-" prefix). The
        // 2026-08-31 cutover happened: that name is now the permanent one for
        // the new estate (dev-np-quickstart.md item 38 is resolved — the
        // registry's token-issuer realm now matches, so np can pull from here
        // directly). "staging-registry-vs" was the pre-cutover name; don't
        // revert to it.
        REGISTRY   = "registry-vs.m-society.go.th"
        PROJECT    = "root"
        REPO       = "vcare-backend"
        BASE_IMAGE = "registry-vs.m-society.go.th/root/vcare-backend"
        IMAGE_TAG  = "${env.GIT_COMMIT?.take(8) ?: 'nogit'}-${env.BUILD_NUMBER}"

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
            //
            // vtn (training env) shares this same np cluster/ns staging with
            // beta (same server, see Jenkinsfile header decision) — its own
            // manifests are stashed alongside beta's rather than in a
            // separate stage, since both branches need this stage's stash
            // name in later node('nonprod') blocks.
            when {
                anyOf {
                    expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
                    expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                }
            }
            steps {
                stash name: 'np-manifests', includes: 'k8s/external-db-np.yml,k8s/case-service-storage-np.yml,k8s/hpa-np.yml,k8s/service-beta.yml,k8s/deployment-beta.yml,k8s/case-service-storage-vtn.yml,k8s/service-vtn.yml,k8s/deployment-vtn.yml,k8s/hpa-vtn.yml'
            }
        }

        stage('Build Docker Images') {
            // vtn never builds — it always deploys whatever tag is currently
            // running in production (see Rollout below), so there is nothing
            // for this stage to do on that branch.
            when {
                expression { return !(env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
            }
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
                                --provenance=false --sbom=false \
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
                                --provenance=false --sbom=false \
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
                                --provenance=false --sbom=false \
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
                                --provenance=false --sbom=false \
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
                                --provenance=false --sbom=false \
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
                                --provenance=false --sbom=false \
                                -t ${BASE_IMAGE}:vcare-dashboard-service${BRANCH_SUFFIX}-${IMAGE_TAG} \
                                -t ${BASE_IMAGE}:vcare-dashboard-service${BRANCH_SUFFIX}-latest \
                                dashboard-service/
                        '''
                    }
                }
            }
        }

        stage('Login Registry') {
            // Only needed ahead of Push Images below — vtn never pushes.
            when {
                expression { return !(env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
            }
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
            // vtn never builds, so there is nothing new to push either.
            when {
                expression { return !(env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
            }
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
                    // Prod's np's Deployments/Services already exist on the cluster,
                    // created and managed by ops (see dev-np-quickstart.md) — this
                    // stage is for ns vcare (prod) only. beta and vtn apply their own
                    // Deployments/Services on np further down ("Ensure np/vtn
                    // Deployments" etc.), not through this stage.
                    when {
                        not {
                            anyOf {
                                expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
                                expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                            }
                        }
                    }
                    steps {
                        sh '''
                            export KUBECONFIG=${KUBECONFIG}
                            kubectl apply -f k8s/external-db.yml
                            kubectl apply -f k8s/case-service-storage.yml
                            kubectl apply -f k8s/service.yml
                            kubectl apply -f k8s/hpa.yml
                        '''
                        // k8s/deployment.yml holds all 6 services with their image field
                        // hardcoded to "<svc>-latest". Re-applying it on every build reverts
                        // whichever service is about to be redeployed back to "-latest" first,
                        // then Rollout below immediately overwrites that with the real build
                        // tag — two writes to the same object a few seconds apart for no
                        // functional gain, and on a control plane with slow disk I/O that's
                        // double the exposure to "spec update not observed" stalls. Only
                        // force-resync the full manifest (picks up replica/resource/label/
                        // pull-secret edits) on a BUILD_ALL run; routine single-service builds
                        // rely on Rollout's set image as the sole write for that Deployment.
                        script {
                            if (params.BUILD_ALL) {
                                sh '''
                                    export KUBECONFIG=${KUBECONFIG}
                                    kubectl apply -f k8s/deployment.yml
                                '''
                            }
                        }
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
                stage('Ensure np Deployments (beta only)') {
                    // Jenkins now owns these Deployments instead of requiring a
                    // one-time hand-applied `kubectl apply -f k8s/deployment-beta.yml`
                    // — idempotent, safe to re-apply every beta run. Must run before
                    // "Ensure np Env Secret"/"Ensure np Pull Secret" below, which
                    // patch these Deployments and would fail if they didn't exist yet.
                    //
                    // Note: deployment-beta.yml's image field is the static
                    // "vcare-<svc>-beta-latest" tag, not the per-build tag Rollout
                    // sets further down — so this apply briefly reverts each
                    // service's image to "-latest" before Rollout's `set image`
                    // overwrites it with the real build tag seconds later, same
                    // documented tradeoff as prod's BUILD_ALL resync of
                    // k8s/deployment.yml. Acceptable here since beta only builds on
                    // a push to that branch, not continuously like prod.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
                    }
                    steps {
                        node('nonprod') {
                            unstash 'np-manifests'
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} apply -f k8s/deployment-beta.yml
                                '''
                            }
                        }
                    }
                }
                stage('Ensure np Services (beta only)') {
                    // Applies k8s/service-beta.yml — see that file's header.
                    // Unlike deployment-beta.yml, this one IS actively applied
                    // by CI, because ocr-service's NodePort doesn't exist on np
                    // yet and nothing else creates it. Idempotent: safe to
                    // re-apply every beta run (existing ClusterIPs are kept —
                    // we don't set spec.clusterIP, so apply won't touch it).
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
                    }
                    steps {
                        node('nonprod') {
                            unstash 'np-manifests'
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} apply -f k8s/service-beta.yml
                                    kubectl -n ${NP_NAMESPACE} get svc
                                '''
                            }
                        }
                    }
                }
                stage('Ensure np HPA (beta only)') {
                    // Applies k8s/hpa-np.yml — see that file's header for which
                    // five services get 2→3 autoscaling and why case-service is
                    // deliberately excluded. Idempotent: safe to re-apply every
                    // beta run.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
                    }
                    steps {
                        node('nonprod') {
                            unstash 'np-manifests'
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} apply -f k8s/hpa-np.yml
                                    kubectl -n ${NP_NAMESPACE} get hpa
                                '''
                            }
                        }
                    }
                }
                stage('Ensure np Env Secret (beta only)') {
                    // Forces every backend Deployment's envFrom back onto our own
                    // "vcare-<svc>-secret-beta" Secret (from k8s/secrets-beta.yml)
                    // on every run — self-healing against anything that resets it
                    // back to the ops-managed "<svc>-env" Secret between deploys.
                    //
                    // k8s/secrets-beta.yml itself is gitignored (real credentials —
                    // Gmail app password, ThaiD client secret, Gemini key, JWT
                    // secrets — never committed) and is NOT applied here: this
                    // stage only patches envFrom to *point at* the Secret by name.
                    // The Secret's actual content has to already exist on the
                    // cluster — apply it by hand once (and again after editing it):
                    //   kubectl -n staging apply -f k8s/secrets-beta.yml
                    // If that Secret is missing entirely, the patch below still
                    // succeeds (it only changes the reference) but the pod will
                    // fail to start with "Secret ... not found" — that's the signal
                    // to go apply k8s/secrets-beta.yml by hand.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('beta') }
                    }
                    steps {
                        node('nonprod') {
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    # deployment name : secret name — "bff-vsmartcare" maps to
                                    # "vcare-bff-secret-beta", not "vcare-bff-vsmartcare-secret-beta"
                                    for pair in \
                                        "bff-vsmartcare:vcare-bff-secret-beta" \
                                        "case-service:vcare-case-service-secret-beta" \
                                        "notification-service:vcare-notification-service-secret-beta" \
                                        "ocr-service:vcare-ocr-service-secret-beta" \
                                        "thaid-auth-service:vcare-thaid-auth-service-secret-beta" \
                                        "dashboard-service:vcare-dashboard-service-secret-beta"; do
                                        d="${pair%%:*}"
                                        s="${pair##*:}"
                                        kubectl -n ${NP_NAMESPACE} patch deployment "$d" --type=json -p \
                                            "[{\\"op\\":\\"replace\\",\\"path\\":\\"/spec/template/spec/containers/0/envFrom/0/secretRef/name\\",\\"value\\":\\"$s\\"}]"
                                    done
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
                stage('Ensure vtn Case-Service Storage (vtn only)') {
                    // Training env, same np cluster/ns staging as beta, but its own
                    // uploads folder — "-vtn" suffix on both the PV path and the PVC
                    // name so training uploads never land in beta's or prod's folder.
                    // See k8s/case-service-storage-vtn.yml.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                    }
                    steps {
                        node('nonprod') {
                            unstash 'np-manifests'
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} apply -f k8s/case-service-storage-vtn.yml

                                    if ! kubectl -n ${NP_NAMESPACE} wait --for=jsonpath='{.status.phase}'=Bound \
                                            pvc/vcare-case-service-uploads-vtn-pvc --timeout=60s; then
                                        echo "--- PVC not Bound, describing ---"
                                        kubectl -n ${NP_NAMESPACE} describe pvc vcare-case-service-uploads-vtn-pvc
                                        kubectl -n ${NP_NAMESPACE} describe pv vcare-case-service-uploads-vtn-pv
                                        exit 1
                                    fi

                                    kubectl -n ${NP_NAMESPACE} get pvc vcare-case-service-uploads-vtn-pvc
                                '''
                            }
                        }
                    }
                }
                stage('Ensure vtn Deployments (vtn only)') {
                    // Jenkins now owns these Deployments instead of requiring a
                    // one-time hand-applied `kubectl apply -f k8s/deployment-vtn.yml`
                    // — idempotent, safe to re-apply every vtn run. Must run before
                    // "Ensure vtn Env Secret"/"Ensure vtn Pull Secret" below, which
                    // patch these Deployments and would fail if they didn't exist yet.
                    //
                    // Unlike beta, this apply writes the exact same static
                    // "vcare-<svc>-latest" tag that Rollout's `set image` below also
                    // writes — no double-write/temporary-downgrade issue here, both
                    // steps agree on the same string.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                    }
                    steps {
                        node('nonprod') {
                            unstash 'np-manifests'
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} apply -f k8s/deployment-vtn.yml
                                '''
                            }
                        }
                    }
                }
                stage('Ensure vtn Services (vtn only)') {
                    // Applies k8s/service-vtn.yml — same idempotent pattern as
                    // "Ensure np Services (beta only)", separate Service objects
                    // named "<svc>-vtn" so they don't collide with beta's.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                    }
                    steps {
                        node('nonprod') {
                            unstash 'np-manifests'
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} apply -f k8s/service-vtn.yml
                                    kubectl -n ${NP_NAMESPACE} get svc
                                '''
                            }
                        }
                    }
                }
                stage('Ensure vtn HPA (vtn only)') {
                    // Applies k8s/hpa-vtn.yml — same idempotent pattern as
                    // "Ensure np HPA (beta only)". Includes case-service-vtn at
                    // parity with prod's hpa.yml — see hpa-vtn.yml's header for
                    // the accepted migration-race tradeoff that comes with it.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                    }
                    steps {
                        node('nonprod') {
                            unstash 'np-manifests'
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} apply -f k8s/hpa-vtn.yml
                                    kubectl -n ${NP_NAMESPACE} get hpa
                                '''
                            }
                        }
                    }
                }
                stage('Ensure vtn Env Secret (vtn only)') {
                    // Self-healing, same pattern as "Ensure np Env Secret (beta
                    // only)" but pointed at each service's own vcare-<svc>-secret-vtn
                    // (separate DB/ThaiD config from both prod and beta — see
                    // k8s/secrets-vtn.yml, gitignored, applied by hand once:
                    //   kubectl -n staging apply -f k8s/secrets-vtn.yml
                    // If that Secret is missing, this patch still succeeds (only the
                    // reference changes) but the pod fails to start with "Secret ...
                    // not found" — that's the signal to go apply it by hand.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                    }
                    steps {
                        node('nonprod') {
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    for pair in \
                                        "bff-vsmartcare-vtn:vcare-bff-secret-vtn" \
                                        "case-service-vtn:vcare-case-service-secret-vtn" \
                                        "notification-service-vtn:vcare-notification-service-secret-vtn" \
                                        "ocr-service-vtn:vcare-ocr-service-secret-vtn" \
                                        "thaid-auth-service-vtn:vcare-thaid-auth-service-secret-vtn" \
                                        "dashboard-service-vtn:vcare-dashboard-service-secret-vtn"; do
                                        d="${pair%%:*}"
                                        s="${pair##*:}"
                                        kubectl -n ${NP_NAMESPACE} patch deployment "$d" --type=json -p \
                                            "[{\\"op\\":\\"replace\\",\\"path\\":\\"/spec/template/spec/containers/0/envFrom/0/secretRef/name\\",\\"value\\":\\"$s\\"}]"
                                    done
                                '''
                            }
                        }
                    }
                }
                stage('Ensure vtn Pull Secret (vtn only)') {
                    // Own pull secret rather than reusing beta's "betabackcred" —
                    // vtn must be able to deploy standalone even if a beta build has
                    // never run on this Jenkins instance. Same devop-bot credential,
                    // same registry, just a separate secret object + name so neither
                    // branch's pipeline run depends on the other having executed first.
                    when {
                        expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
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
                                        kubectl -n ${NP_NAMESPACE} create secret docker-registry vtnbackcred \
                                            --docker-server=${REGISTRY} \
                                            --docker-username="$REGISTRY_USER" \
                                            --docker-password="$REGISTRY_PASS" \
                                            --dry-run=client -o yaml | kubectl apply -f -

                                        for d in bff-vsmartcare-vtn case-service-vtn notification-service-vtn \
                                                 ocr-service-vtn thaid-auth-service-vtn dashboard-service-vtn; do
                                            kubectl -n ${NP_NAMESPACE} patch deployment "$d" --type=json -p \
                                                '[{"op":"add","path":"/spec/template/spec/imagePullSecrets","value":[{"name":"regcred"},{"name":"regcred-staging"},{"name":"vtnbackcred"}]}]'
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
                                    expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                                }
                            }
                            steps {
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('vtn')) {
                                        // Always the current production tag — vtn never builds its
                                        // own image (see Build Docker Images), it just tracks whatever
                                        // is live in prod. imagePullPolicy: Always on the Deployment
                                        // means even an unchanged tag re-pulls if prod pushed a new
                                        // ":latest" since the last vtn rollout.
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/bff-vsmartcare-vtn \
                                                        '*'=${BASE_IMAGE}:vcare-bff-latest
                                                    # set image is a no-op when the tag string is unchanged (always true
                                                    # here — vtn always targets the same static "-latest" tag), so force
                                                    # a restart every run to actually re-pull under imagePullPolicy: Always
                                                    kubectl -n ${NP_NAMESPACE} rollout restart deployment/bff-vsmartcare-vtn
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/bff-vsmartcare-vtn --timeout=600s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/bff-vsmartcare-vtn
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=bff-vsmartcare-vtn
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else if (branchName.contains('beta')) {
                                        // np's Deployment for this service is "bff-vsmartcare",
                                        // not "vcare-bff" — see dev-np-quickstart.md §4. '*'
                                        // sidesteps needing the exact container name.
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/bff-vsmartcare \
                                                        '*'=${BASE_IMAGE}:vcare-bff${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/bff-vsmartcare --timeout=600s; then
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
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-bff --timeout=600s
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
                                    expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                                }
                            }
                            steps {
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('vtn')) {
                                        // case-service-vtn now scales 2→3 via hpa-vtn.yml, at parity
                                        // with prod — rollout restart here rolls each replica in turn
                                        // the same way a normal Deployment update would.
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/case-service-vtn \
                                                        '*'=${BASE_IMAGE}:vcare-case-service-latest
                                                    kubectl -n ${NP_NAMESPACE} rollout restart deployment/case-service-vtn
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/case-service-vtn --timeout=600s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/case-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=case-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else if (branchName.contains('beta')) {
                                        // case-service now scales 2→3 via hpa-np.yml, at parity with
                                        // prod — see that file's header for the accepted migration-race
                                        // tradeoff.
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/case-service \
                                                        '*'=${BASE_IMAGE}:vcare-case-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/case-service --timeout=600s; then
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
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-case-service --timeout=600s
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
                                    expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                                }
                            }
                            steps {
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('vtn')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/notification-service-vtn \
                                                        '*'=${BASE_IMAGE}:vcare-notification-service-latest
                                                    kubectl -n ${NP_NAMESPACE} rollout restart deployment/notification-service-vtn
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/notification-service-vtn --timeout=600s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/notification-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=notification-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else if (branchName.contains('beta')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/notification-service \
                                                        '*'=${BASE_IMAGE}:vcare-notification-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/notification-service --timeout=600s; then
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
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-notification-service --timeout=600s
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
                                    expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                                }
                            }
                            steps {
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('vtn')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/ocr-service-vtn \
                                                        '*'=${BASE_IMAGE}:vcare-ocr-service-latest
                                                    kubectl -n ${NP_NAMESPACE} rollout restart deployment/ocr-service-vtn
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/ocr-service-vtn --timeout=600s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/ocr-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=ocr-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else if (branchName.contains('beta')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/ocr-service \
                                                        '*'=${BASE_IMAGE}:vcare-ocr-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/ocr-service --timeout=600s; then
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
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-ocr-service --timeout=600s
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
                                    expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                                }
                            }
                            steps {
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('vtn')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/thaid-auth-service-vtn \
                                                        '*'=${BASE_IMAGE}:vcare-thaid-auth-service-latest
                                                    kubectl -n ${NP_NAMESPACE} rollout restart deployment/thaid-auth-service-vtn
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/thaid-auth-service-vtn --timeout=600s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/thaid-auth-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=thaid-auth-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else if (branchName.contains('beta')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/thaid-auth-service \
                                                        '*'=${BASE_IMAGE}:vcare-thaid-auth-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/thaid-auth-service --timeout=600s; then
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
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-thaid-auth-service --timeout=600s
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
                                    expression { return (env.BRANCH_NAME ?: env.GIT_BRANCH ?: '').contains('vtn') }
                                }
                            }
                            steps {
                                script {
                                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                                    if (branchName.contains('vtn')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/dashboard-service-vtn \
                                                        '*'=${BASE_IMAGE}:vcare-dashboard-service-latest
                                                    kubectl -n ${NP_NAMESPACE} rollout restart deployment/dashboard-service-vtn
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/dashboard-service-vtn --timeout=600s; then
                                                        echo "--- rollout failed, describing ---"
                                                        kubectl -n ${NP_NAMESPACE} describe deployment/dashboard-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=dashboard-service-vtn
                                                        kubectl -n ${NP_NAMESPACE} get events --sort-by=.lastTimestamp | tail -30
                                                        exit 1
                                                    fi
                                                '''
                                            }
                                        }
                                    } else if (branchName.contains('beta')) {
                                        node('nonprod') {
                                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                                sh '''
                                                    kubectl -n ${NP_NAMESPACE} set image deployment/dashboard-service \
                                                        '*'=${BASE_IMAGE}:vcare-dashboard-service${BRANCH_SUFFIX}-${IMAGE_TAG}
                                                    if ! kubectl -n ${NP_NAMESPACE} rollout status deployment/dashboard-service --timeout=600s; then
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
                                            kubectl -n ${NAMESPACE} rollout status deployment/vcare-dashboard-service --timeout=600s
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
                    if (branchName.contains('vtn')) {
                        node('nonprod') {
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} get deployment \
                                        bff-vsmartcare-vtn case-service-vtn notification-service-vtn \
                                        ocr-service-vtn thaid-auth-service-vtn dashboard-service-vtn
                                    kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=bff-vsmartcare-vtn
                                    kubectl -n ${NP_NAMESPACE} get pods -o wide -l app=case-service-vtn

                                    echo "--- envFrom secret per Deployment ---"
                                    for d in bff-vsmartcare-vtn case-service-vtn notification-service-vtn \
                                             ocr-service-vtn thaid-auth-service-vtn dashboard-service-vtn; do
                                        echo -n "$d: "
                                        kubectl -n ${NP_NAMESPACE} get deploy "$d" \
                                            -o jsonpath='{.spec.template.spec.containers[0].envFrom}'
                                        echo
                                    done
                                '''
                            }
                        }
                    } else if (branchName.contains('beta')) {
                        node('nonprod') {
                            withEnv(["KUBECONFIG=${NP_KUBECONFIG}"]) {
                                sh '''
                                    kubectl -n ${NP_NAMESPACE} get deployment \
                                        bff-vsmartcare case-service notification-service \
                                        ocr-service thaid-auth-service dashboard-service
                                    kubectl -n ${NP_NAMESPACE} get pods -o wide

                                    echo "--- envFrom secret per Deployment ---"
                                    for d in bff-vsmartcare case-service notification-service \
                                             ocr-service thaid-auth-service dashboard-service; do
                                        echo -n "$d: "
                                        kubectl -n ${NP_NAMESPACE} get deploy "$d" \
                                            -o jsonpath='{.spec.template.spec.containers[0].envFrom}'
                                        echo
                                    done
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
            echo " Tag : ${env.IMAGE_TAG}"
            echo "======================================"
        }

        failure {
            echo "======================================"
            echo " Deploy Failed"
            echo " Tag : ${env.IMAGE_TAG}"
            echo "======================================"
        }
    }
}
