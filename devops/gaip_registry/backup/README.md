* crt
pull 하는 Node의 ca_file 경로에 registry 에 적용된 crt 파일을 옮기기

* containerd config
      [plugins."io.containerd.grpc.v1.cri".registry.configs]   
        [plugins."io.containerd.grpc.v1.cri".registry.configs."$REGISTRYIP:$REGISTRYPORT"]   
          [plugins."io.containerd.grpc.v1.cri".registry.configs."$REGISTRYIP:$REGISTRYPORT".tls]   
            ca_file = ""   
            cert_file = ""   
            insecure_skip_verify = true   
            key_file = ""   

      [plugins."io.containerd.grpc.v1.cri".registry.headers]   
      [plugins."io.containerd.grpc.v1.cri".registry.mirrors]   
        [plugins."io.containerd.grpc.v1.cri".registry.mirrors."$REGISTRYIP:$REGISTRYPORT"]   
          endpoint = ["http://$REGISTRYIP:$REGISTRYPORT"]   
