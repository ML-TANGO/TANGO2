{{- define "command" -}}
{{- if and (eq .Values.common.imageType "pull")  -}}
{{ include "dockerPull" . }}
{{- else if (eq .Values.common.imageType "build") -}}
{{ include "dockerBuild" . }}
{{- else if (eq .Values.common.imageType "tar") -}}
{{ include "dockerTar" . }}
{{- else if (eq .Values.common.imageType "ngc") -}}
{{ include "dockerNgc" . }}
{{- else if (eq .Values.common.imageType "copy") -}}
{{ include "dockerCopy" . }}
{{- else if and (eq .Values.common.imageType "commit" ) (eq .Values.common.systemContainerRuntime "containerd") -}}
{{ include "nerdctlCommit" . }}
{{- else if and ( eq .Values.common.imageType "commit") (eq .Values.common.systemContainerRuntime "docker") -}}
{{ include "dockerCommit" . }}
{{- else if and (eq .Values.common.imageType "tag" ) (eq .Values.common.systemContainerRuntime "containerd") -}}
{{ include "nerdctlTag" . }}
{{- else if and ( eq .Values.common.imageType "tag") (eq .Values.common.systemContainerRuntime "docker") -}}
{{ include "dockerTag" . }}
{{- end }}
{{- end }}


{{/*============================================================================================================*/}}
{{/*Container runtime 상관없이 dockerd 사용*/}}
{{/*build, tar 실패시 파일 삭제안하고 남겨두도록 커맨드 작성함*/}}
{{/*============================================================================================================*/}}

{{- define "dockerPull" -}}
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/" }} --insecure-registry {{ .Values.common.userRegistryUrl | trimSuffix "/" }} &
echo "Waiting for Docker daemon to be ready..."
until docker info > /dev/null 2>&1; do
  sleep 1
done

echo "Checking insecure registry configuration..."
docker info | grep -A2 "Insecure Registries"
if [ $? -ne 0 ]; then
  echo "Docker daemon is not configured to use insecure registries. Exiting."
  exit 1
fi

echo "Docker daemon is ready. Pulling image..."
for i in {1..5}; do
  docker pull {{ .Values.pull.pullImageUrl }} && break
  echo "Retrying docker pull... ($i)"
  sleep 2
done

docker tag {{ .Values.pull.pullImageUrl }} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};
{{- end }}

{{- define "dockerBuild" -}}
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/" }} --insecure-registry {{ .Values.common.userRegistryUrl | trimSuffix "/" }} &
sleep 5;
docker build --no-cache --tag {{ .Values.common.imageName }} --file /jf-data/images/{{ .Values.build.filePath }} . ;
if docker push {{ .Values.common.imageName }}; then 
rm /jf-data/images/{{ .Values.build.filePath }};
fi
{{- end }}

{{- define "dockerTar" -}}
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/" }} --insecure-registry {{ .Values.common.userRegistryUrl | trimSuffix "/" }} &
sleep 5;
LOADED_IMAGE=$(docker load --input /jf-data/images/{{ .Values.tar.filePath }});
LOADED_IMAGE_NAME=$(echo ${LOADED_IMAGE} | grep 'Loaded image:' | awk -F ': ' '{print $2}');
echo ${LOADED_IMAGE_NAME};
docker tag ${LOADED_IMAGE_NAME} {{ .Values.common.imageName }};
if docker push {{ .Values.common.imageName }}; then 
rm /jf-data/images/{{ .Values.tar.filePath }};
fi
{{- end }}

{{- define "dockerNgc" -}}
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/" }} --insecure-registry {{ .Values.common.userRegistryUrl | trimSuffix "/" }} &
sleep 5;
ngc registry image pull {{ .Values.ngc.pullImageUrl }};
docker tag {{ .Values.ngc.pullImageUrl }} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};
{{- end }}

{{- define "dockerCopy" -}}
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/" }} --insecure-registry {{ .Values.common.userRegistryUrl | trimSuffix "/" }} &
sleep 5;
docker pull {{ .Values.copy.pullImageUrl }};
docker tag {{ .Values.copy.pullImageUrl }} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};
{{- end }}

{{/*============================================================================================================*/}}
{{/*Container runtime 에 따라서 달라짐*/}}
{{/*============================================================================================================*/}}

{{- define "nerdctlCommit" -}}
POD_NAME=$(nerdctl --namespace k8s.io ps | grep {{ .Values.commit.trainingPodName }}/ | grep -v registry.k8s.io | awk '{print $1}');
ORIGIN_IMAGE=$(nerdctl --namespace k8s.io ps | grep {{ .Values.commit.trainingPodName }}/ | grep -v registry.k8s.io | awk '{print $2}');

# ORIGIN_IMAGE에서 레지스트리 URL 추출
ORIGIN_REGISTRY=$(echo $ORIGIN_IMAGE | cut -d'/' -f1)
# 목적지 이미지에서 레지스트리 URL 추출  
DEST_REGISTRY=$(echo {{ .Values.common.imageName }} | cut -d'/' -f1)

# 도메인인지 IP인지 판단하는 함수
is_ip_address() {
  # 포트가 있는 경우 포트 제거
  host=$(echo $1 | cut -d':' -f1)
  
  # 점이 3개 있고 각 섹션이 숫자로만 구성되어 있는지 확인
  echo $host | grep -E '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$' > /dev/null 2>&1
  return $?
}

# ORIGIN_IMAGE pull 시 플래그 결정
if is_ip_address $ORIGIN_REGISTRY; then
  ORIGIN_PULL_FLAGS="--plain-http"
  echo "ORIGIN_REGISTRY is IP address: $ORIGIN_REGISTRY, using --plain-http"
else
  ORIGIN_PULL_FLAGS=""
  echo "ORIGIN_REGISTRY is domain: $ORIGIN_REGISTRY, using HTTPS"
fi

# 목적지 이미지 push 시 플래그 결정
if is_ip_address $DEST_REGISTRY; then
  DEST_PUSH_FLAGS="--plain-http"
  echo "DEST_REGISTRY is IP address: $DEST_REGISTRY, using --plain-http"
else
  DEST_PUSH_FLAGS=""
  echo "DEST_REGISTRY is domain: $DEST_REGISTRY, using HTTPS"
fi

echo ctr --namespace k8s.io image pull $ORIGIN_PULL_FLAGS $ORIGIN_IMAGE;
ctr --namespace k8s.io image pull $ORIGIN_PULL_FLAGS $ORIGIN_IMAGE;
echo nerdctl commit --namespace k8s.io --pause=false $POD_NAME {{ .Values.common.imageName }};
nerdctl commit --namespace k8s.io --pause=false $POD_NAME {{ .Values.common.imageName }} --change 'CMD [""]' --change 'ENTRYPOINT [""]' --message '{{ .Values.commit.commitMessage }}';
ctr --namespace k8s.io image push $DEST_PUSH_FLAGS {{ .Values.common.imageName }};
{{- end }}

{{- define "dockerCommit" -}}
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/" }} --insecure-registry {{ .Values.common.userRegistryUrl | trimSuffix "/" }} &
sleep 5;
POD_NAME=$(docker ps | grep {{ .Values.commit.trainingPodName }} | grep -v pause | awk '{print $1}');
echo docker commit --change \'CMD [\"\"]\' --change \'ENTRYPOINT [\"\"]\' $POD_NAME {{ .Values.common.imageName }};
docker commit --change \'CMD [\"\"]\' --change \'ENTRYPOINT [\"\"]\' ${POD_NAME} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};
{{- end }}

{{- define "dockerTag" -}}
dockerd --insecure-registry {{ .Values.common.systemRegistryUrl | trimSuffix "/" }} --insecure-registry {{ .Values.common.userRegistryUrl | trimSuffix "/" }} &
sleep 5;
docker tag {{ .Values.tag.tagImageUrl }} {{ .Values.common.imageName }};
docker push {{ .Values.common.imageName }};
{{- end }}

{{- define "nerdctlTag" -}}
containerd &
sleep 5;
nerdctl tag {{ .Values.tag.tagImageUrl }} {{ .Values.common.imageName }};
nerdctl push --insecure-registry {{ .Values.common.imageName }};
{{- end }}

{{/*============================================================================================================*/}}
{{/*NERDCTL X 사용 안함*/}}
{{/*============================================================================================================*/}}

{{- define "nerdctlBuild" -}}
buildkitd --addr unix:///run/buildkit/buildkitd.sock &
buildkitd --addr unix:///run/buildkit/buildkitd.sock &
sleep 5;
containerd &
sleep 5;
nerdctl build --no-cache --tag {{ .Values.common.imageName }} --file /jf-data/images/{{ .Values.build.filePath }} . ;
nerdctl push --insecure-registry {{ .Values.common.imageName }};
rm /jf-data/images/{{ .Values.build.filePath }};
{{- end }}
