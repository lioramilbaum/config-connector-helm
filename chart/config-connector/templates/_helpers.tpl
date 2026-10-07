{{/*
Expand the name of the chart.
*/}}
{{- define "config-connector.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "config-connector.fullname" -}}
{{- if contains .Chart.Name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "config-connector.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels for all resources
*/}}
{{- define "config-connector.labels" -}}
helm.sh/chart: {{ include "config-connector.chart" . }}
app.kubernetes.io/name: {{ include "config-connector.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{ with .Values.commonLabels }}{{ toYaml . }}{{ end }}
{{- end }}

{{/*
Construct the container image string from repository, tag, digest, and appVersion
Expects to be called with full context: include "config-connector.image" .
*/}}
{{- define "config-connector.image" -}}
{{- $repo := .Values.image.repository | default "gcr.io/gke-release/cnrm/operator" }}
{{- $tag := .Values.image.tag | default .Chart.AppVersion }}
{{- $image := printf "%s:%s" $repo $tag }}
{{- if .Values.image.digest }}
{{- printf "%s@%s" $repo .Values.image.digest }}
{{- else }}
{{- $image }}
{{- end }}
{{- end }}
