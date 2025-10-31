{{- define "command" -}}
{{- if and (eq .Values.common.imageType "ngc")  -}}
{{ include "commandNgc" . }}
{{- else if (eq .Values.common.imageType "tag") -}}
{{ include "commandTag" . }}
{{- else if and (eq .Values.common.imageType "commit" ) (eq .Values.common.systemContainerRuntime "containerd") -}}
{{ include "commandCommit" . }}
{{- else if and ( eq .Values.common.imageType "build") (eq .Values.common.systemContainerRuntime "containerd") -}}
{{ include "commandBuild" . }}
{{- else if and (eq .Values.common.imageType "pull") (eq .Values.common.systemContainerRuntime "containerd") -}}
{{ include "commandPull" . }}
{{- else if and (eq .Values.common.imageType "tar")  (eq .Values.common.systemContainerRuntime "containerd") -}}
{{ include "commandTar" . }}
{{- else if and (eq .Values.common.imageType "copy")  (eq .Values.common.systemContainerRuntime "containerd") -}}
{{ include "commandCopy" . }}
{{- else if and (eq .Values.common.imageType "commit" ) (eq .Values.common.systemContainerRuntime "docker") -}}
{{ include "dockerCommit" . }}
{{- else if and ( eq .Values.common.imageType "build") (eq .Values.common.systemContainerRuntime "docker") -}}
{{ include "dockerBuild" . }}
{{- else if and (eq .Values.common.imageType "pull") (eq .Values.common.systemContainerRuntime "docker") -}}
{{ include "dockerPull" . }}
{{- else if and (eq .Values.common.imageType "tar")  (eq .Values.common.systemContainerRuntime "docker") -}}
{{ include "dockerTar" . }}
{{- else if and (eq .Values.common.imageType "copy")  (eq .Values.common.systemContainerRuntime "docker") -}}
{{ include "dockerCopy" . }}
{{- end }}
{{- end }}


{{- define "commandCommit" -}}
"POD_NAME=$(nerdctl --namespace k8s.io ps | grep {{ .Values.commit.trainingPodName }} | grep -v registry.k8s.io | awk '{print $1}');
ORIGIN_IMAGE=$(nerdctl --namespace k8s.io ps | grep {{ .Values.commit.trainingPodName }} | grep -v registry.k8s.io | awk '{print $2}');
echo ctr --namespace k8s.io image pull --plain-http $ORIGIN_IMAGE;
ctr --namespace k8s.io image pull --plain-http $ORIGIN_IMAGE
echo nerdctl commit --namespace k8s.io --pause=false $POD_NAME;
nerdctl commit --namespace k8s.io --pause=false ${POD_NAME} --change \'CMD [\"\"]\' --change \'ENTRYPOINT [\"\"]\' --message {{ .Values.commit.commitMessage }} {{ .Values.common.imageName }};
ctr --namespace k8s.io image push --plain-http {{ .Values.common.imageName }};"
{{- end }}

{{- define "commandNgc" -}}
"dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
sleep 5;
ngc registry image pull {{ .Values.ngc.pullImageUrl }};
docker tag {{ .Values.ngc.pullImageUrl }} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};"
{{- end }}

{{- define "commandPull" -}}
"containerd &
sleep 5;
echo nerdctl pull --unpack=false {{ .Values.pull.pullImageUrl }};
nerdctl pull --unpack=false {{ .Values.pull.pullImageUrl }};
nerdctl tag {{ .Values.pull.pullImageUrl }} {{ .Values.common.imageName }};
nerdctl push --insecure-registry {{ .Values.common.imageName }};"
{{- end }}

{{- define "commandCopy" -}}
"nerdctl pull --unpack=false --insecure-registry  {{ .Values.copy.pullImageUrl }};
nerdctl tag {{ .Values.copy.pullImageUrl }} {{ .Values.common.imageName }};
nerdctl push --insecure-registry {{ .Values.common.imageName }};"
{{- end }}

{{- define "commandTag" -}}
"containerd &
sleep 5;
nerdctl tag {{ .Values.tag.tagImageUrl }} {{ .Values.common.imageName }};
nerdctl push --insecure-registry {{ .Values.common.imageName }};"
{{- end }}

{{- define "commandBuild" -}}
"buildkitd --addr unix:///run/buildkit/buildkitd.sock &
buildkitd --addr unix:///run/buildkit/buildkitd.sock &
sleep 5;
containerd &
sleep 5;
nerdctl build --no-cache --tag {{ .Values.common.imageName }} --file /jf-data/images/{{ .Values.build.filePath }} . ;
nerdctl push --insecure-registry {{ .Values.common.imageName }};
rm /jf-data/images/{{ .Values.build.filePath }};"
{{- end }}

{{- define "commandTar" -}}
"containerd &
sleep 5;
LOADED_IMAGE=$(nerdctl load --input /jf-data/images/{{ .Values.tar.filePath }});
LOADED_IMAGE_NAME=$(echo ${LOADED_IMAGE} | grep 'Loaded image:' | awk -F ': ' '{print $2}');
echo ${LOADED_IMAGE_NAME};
nerdctl tag ${LOADED_IMAGE_NAME} {{ .Values.common.imageName }};
nerdctl push --insecure-registry {{ .Values.common.imageName }};
rm /jf-data/images/{{ .Values.tar.filePath }};"
{{- end }}




{{- define "dockerCommit" -}}
"dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
sleep 5;
POD_NAME=$(docker ps | grep {{ .Values.commit.trainingPodName }} | grep -v pause | awk '{print $1}');
echo docker commit --change \'CMD [\"\"]\' --change \'ENTRYPOINT [\"\"]\' $POD_NAME {{ .Values.common.imageName }};
docker commit --change \'CMD [\"\"]\' --change \'ENTRYPOINT [\"\"]\' ${POD_NAME} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};"
{{- end }}

{{- define "dockerBuild" -}}
"dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
sleep 5;
docker build --no-cache --tag {{ .Values.common.imageName }} --file /jf-data/images/{{ .Values.build.filePath }} . ;
docker push {{ .Values.common.imageName }};
{{- end }}

{{- define "dockerPull" -}}
"dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
sleep 5;
echo docker pull {{ .Values.pull.pullImageUrl }};
docker pull {{ .Values.pull.pullImageUrl }};
docker tag {{ .Values.pull.pullImageUrl }} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};"
{{- end }}

{{- define "dockerTar" -}}
"dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
sleep 5;
LOADED_IMAGE=$(docker load --input /jf-data/images/{{ .Values.tar.filePath }});
LOADED_IMAGE_NAME=$(echo ${LOADED_IMAGE} | grep 'Loaded image:' | awk -F ': ' '{print $2}');
echo ${LOADED_IMAGE_NAME};
docker tag ${LOADED_IMAGE_NAME} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};
rm /jf-data/images/{{ .Values.tar.filePath }};"
{{- end }}

{{- define "dockerCopy" -}}
"dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/"  }} &
sleep 5;
docker pull {{ .Values.copy.pullImageUrl }};
docker tag {{ .Values.copy.pullImageUrl }} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};"
{{- end }}