{{- define "sentinel.configFiles" -}}
{{- $values := .Values -}}
{{- $sre := $values.agents.sre.enabled -}}
{{- $review := (index $values.agents "pr-review").enabled -}}
{{- $topicNames := dict -}}
{{- range $key, $topic := $values.kafka.topics -}}
{{- $_ := set $topicNames $key $topic.name -}}
{{- end -}}
{{- $agents := list -}}
{{- range $agent := keys $values.agents | sortAlpha -}}
{{- if (index $values.agents $agent).enabled -}}
{{- $agents = append $agents $agent -}}
{{- end -}}
{{- end -}}
{{- $sreRun := int $values.agents.sre.runTimeoutSeconds -}}
{{- $reviewRun := int (index $values.agents "pr-review").runTimeoutSeconds -}}
{{- $executorAction := int $values.executor.actionTimeoutSeconds -}}
{{- $longestWork := max $sreRun $reviewRun $executorAction -}}
{{- $site := dict
  "common/agents.yaml" (dict "agents" $agents)
  "common/kafka.yaml" (dict "kafka" (dict "bootstrap_servers" $values.kafka.bootstrapServers "consumer_group" $values.kafka.consumerGroup "topics" $topicNames "max_poll_interval_seconds" (mul $longestWork 2)))
  "common/s3.yaml" (dict "s3" $values.s3)
  "common/database.yaml" (dict "database" (dict "host" $values.postgres.host "name" $values.postgres.database "user" $values.postgres.user))
  "common/clickhouse.yaml" (dict "clickhouse" (dict "host" $values.clickhouse.host "database" $values.clickhouse.database "user" $values.clickhouse.user))
  "common/knowledge-api.yaml" (dict "knowledge" (dict "endpoint" (printf "http://sentinel-knowledge.%s.svc.cluster.local:9092" .Release.Namespace)))
  "knowledge.yaml" (dict "knowledge_database_user" $values.postgres.knowledgeUser)
  "workflow.yaml" (dict "sre" (dict "alertmanager" (dict "url" $values.alertmanager.url) "incident" (dict "workflow_timeout_seconds" $sreRun)) "pr_review" (dict "workflow_timeout_seconds" $reviewRun))
  "sre.yaml" (dict "prometheus" (dict "url" $values.prometheus.url) "limits" (dict "run_timeout_seconds" $sreRun))
  "pr-review.yaml" (dict "review" (dict "run_timeout_seconds" $reviewRun))
  "executor.yaml" (dict "executor" (dict "action_timeout_seconds" $executorAction))
-}}
{{- $files := dict -}}
{{- range $name := list "common/logging.yaml" "common/agents.yaml" "common/repositories.yaml" "common/database.yaml" "common/kafka.yaml" "common/s3.yaml" "common/clickhouse.yaml" "common/llm.yaml" "common/knowledge-api.yaml" "workflow.yaml" "executor.yaml" "knowledge.yaml" "sre.yaml" "pr-review.yaml" -}}
{{- $config := $.Files.Get (printf "config/%s" $name) | fromYaml -}}
{{- $config = mergeOverwrite $config (index $site $name | default dict) -}}
{{- if eq $name "workflow.yaml" -}}
{{- if not $sre }}{{ $_ := unset $config "sre" }}{{ end -}}
{{- if not $review }}{{ $_ := unset $config "pr_review" }}{{ end -}}
{{- end -}}
{{- $_ := set $files (base $name) ($config | toYaml) -}}
{{- end -}}
{{- toYaml $files -}}
{{- end -}}
