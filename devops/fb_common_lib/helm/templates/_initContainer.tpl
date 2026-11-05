{{- define "lib.initContainer.db" -}}
- name: wait-for-jfb-db
  image: mariadb:10.11
  command: ['sh', '-c']
  args:
  - until mysql -h ${JF_DB_HOST} -u root -p${JF_DB_PW} -e "SHOW DATABASES LIKE '${JF_DB_NAME}'" | grep -q ${JF_DB_NAME}; do echo "Waiting for database '${JF_DB_NAME}' connection..."; sleep 1; done;
  env:
  - name: JF_DB_HOST
    valueFrom:
      configMapKeyRef:
        name: jfb-settings
        key: JF_DB_HOST
  - name: JF_DB_PW  # TODO 시크릿 사용
    valueFrom:
      configMapKeyRef:
        name: jfb-settings
        key: JF_DB_PW
  - name: JF_DB_NAME
    valueFrom:
      configMapKeyRef:
        name: jfb-settings
        key: JF_DB_NAME
{{- end -}}
