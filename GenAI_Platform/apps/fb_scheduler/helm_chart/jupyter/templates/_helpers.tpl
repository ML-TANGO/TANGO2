
{{- define "namespace" -}}
{{ $.Values.system.namespace }}-{{ $.Values.labels.workspace_id }}
{{- end }}

{{- define "update_jupyter" -}}
    {{- if ne .Values.labels.training_tool_type "editor" }}
        cd $JF_HOME && export SHELL=/bin/bash && jupyter lab --allow-root --ip 0.0.0.0 --notebook-dir $JF_HOME --NotebookApp.base_url=/jupyter/{{ .Values.pod_name }}/ --NotebookApp.allow_origin=*           

        curl --version || apt install -y curl --no-install-recommends || ( apt update; apt install -y curl --no-install-recommends)                                                                                        
        git --version || apt install -y git --no-install-recommends                                                                                                                                                        
        pip3 --version || (apt-get install -y python3-distutils; curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py; python3 get-pip.py --force-reinstall; rm get-pip.py)                                             
        pip3 --version || (apt-get install -y python3-distutils; curl https://bootstrap.pypa.io/pip/3.6/get-pip.py -o get-pip.py; python3 get-pip.py --force-reinstall; rm get-pip.py)                                     
                                                                                                                                                                                                                            
        pip3 uninstall -y jupyter-core || pip3 install jupyter-core==4.7.1                                                                                                                                                 
        pip3 list | grep 'jupyterlab ' | grep 3.1.1  || pip3 install jupyterlab==3.1.1                                                                                                                                     
        pip3 list | grep 'jupyterlab-git ' | grep 0.30.0 || pip3 install jupyterlab-git==0.30.0                                                                                                                            
                                                                                                                                                                                                                            
        pip3 install | grep 'ipympl' | grep 0.7.0 || pip3 install ipympl; jupyter labextension install @jupyter-widgets/jupyterlab-manager jupyter-matplotlib 
    {{- end}}
{{- end }}


{{- define "name" -}}
{{ $.Values.system.namespace }}-{{ $.Values.labels.workspace_id }}
{{- end }}