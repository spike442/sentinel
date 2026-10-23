{{- define "sentinel.standardLabels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name (.Chart.Version | replace "+" "_") | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service | quote }}
app.kubernetes.io/instance: {{ .Release.Name | quote }}
{{- end -}}

{{- define "sentinel.anyAgentEnabled" -}}
{{- if .Values.agents.sre.enabled }}true{{ end -}}
{{- end -}}

{{- define "sentinel.egress.dns" -}}
- toEndpoints:
  - matchLabels:
      k8s:io.kubernetes.pod.namespace: kube-system
      k8s-app: kube-dns
  toPorts:
  - ports:
    - {port: "53", protocol: ANY}
{{- end -}}

{{- define "sentinel.egress.apiserver" -}}
- toEntities: [kube-apiserver]
{{- end -}}

{{- define "sentinel.egress.knowledge" -}}
- toEndpoints:
  - matchLabels:
      app.kubernetes.io/name: sentinel-knowledge
  toPorts:
  - ports:
    - {port: "9092", protocol: TCP}
{{- end -}}

{{- define "sentinel.egress.prometheus" -}}
- toEndpoints:
  - matchLabels:
      k8s:io.kubernetes.pod.namespace: {{ .Values.networkPolicy.monitoringNamespace }}
      app.kubernetes.io/name: prometheus
  toPorts:
  - ports:
    - {port: "9090", protocol: TCP}
{{- end -}}

{{- define "sentinel.egress.storage" -}}
- toEndpoints:
  - matchLabels:
      k8s:io.kubernetes.pod.namespace: {{ .Values.networkPolicy.storageNamespace }}
  toPorts:
  - ports:
    - {port: "9000", protocol: TCP}
{{- end -}}

{{- define "sentinel.egress.messaging" -}}
- toEndpoints:
  - matchLabels:
      k8s:io.kubernetes.pod.namespace: {{ .Values.networkPolicy.messagingNamespace }}
  toPorts:
  - ports:
    - {port: "9093", protocol: TCP}
{{- end -}}

{{- define "sentinel.egress.internet" -}}
- toEntities: [world]
  toPorts:
  - ports:
    - {port: "443", protocol: TCP}
{{- end -}}
