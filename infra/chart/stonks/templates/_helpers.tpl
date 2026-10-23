{{- define "stonks.standardLabels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name (.Chart.Version | replace "+" "_") | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service | quote }}
app.kubernetes.io/instance: {{ .Release.Name | quote }}
app.kubernetes.io/part-of: stonks
{{- end -}}

{{- define "stonks.serviceAccount" -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  labels:
    app.kubernetes.io/name: {{ .name }}
{{ include "stonks.standardLabels" .root | indent 4 }}
  name: {{ .name }}
  namespace: {{ .root.Release.Namespace }}
{{- if .withoutToken }}
automountServiceAccountToken: false
{{- end }}
{{- end -}}
