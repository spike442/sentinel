{{- define "sentinel.serviceAccount" -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  labels:
    app.kubernetes.io/name: sentinel
{{ include "sentinel.standardLabels" .root | indent 4 }}
  name: {{ .name }}
  namespace: {{ .root.Release.Namespace }}
{{- end -}}

{{- define "sentinel.clusterRoleBinding" -}}
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  labels:
    app.kubernetes.io/name: sentinel
{{ include "sentinel.standardLabels" .root | indent 4 }}
  name: {{ .role }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: {{ .role }}
subjects:
- kind: ServiceAccount
  name: {{ .account }}
  namespace: {{ .root.Release.Namespace }}
{{- end -}}

{{- define "sentinel.kubeconfig" -}}
apiVersion: v1
kind: ConfigMap
metadata:
  labels:
    app.kubernetes.io/name: sentinel
{{ include "sentinel.standardLabels" .root | indent 4 }}
  name: {{ .configMap }}
  namespace: {{ .root.Release.Namespace }}
data:
  config: |
    apiVersion: v1
    kind: Config
    clusters:
    - name: in-cluster
      cluster:
        server: https://kubernetes.default.svc
        certificate-authority: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
    users:
    - name: {{ .user }}
      user:
        tokenFile: /var/run/secrets/kubernetes.io/serviceaccount/token
    contexts:
    - name: {{ .user }}
      context:
        cluster: in-cluster
        user: {{ .user }}
        namespace: {{ .root.Release.Namespace }}
    current-context: {{ .user }}
{{- end -}}
