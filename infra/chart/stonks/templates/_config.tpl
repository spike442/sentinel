{{- define "stonks.configFiles" -}}
{{- $values := .Values -}}
{{- $site := dict
  "common/s3.yaml" (dict "s3" $values.s3)
  "common/llm.yaml" (dict "llm" $values.llm)
  "dividends.yaml" (dict "search" (dict "url" $values.search.url))
-}}
{{- $files := dict -}}
{{- range $name := list "common/logging.yaml" "common/s3.yaml" "common/storage.yaml" "common/llm.yaml" "ingest.yaml" "dividends.yaml" -}}
{{- $config := $.Files.Get (printf "config/%s" $name) | fromYaml | default dict -}}
{{- $config = mergeOverwrite $config (index $site $name | default dict) -}}
{{- $_ := set $files (base $name) ($config | toYaml) -}}
{{- end -}}
{{- toYaml $files -}}
{{- end -}}
