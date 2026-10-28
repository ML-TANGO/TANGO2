package main

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const sampleBuildYAML = `apiVersion: sdx/v1
kind: ImageBuild
metadata:
  name: my-app
  tag: 1.0.0
spec:
  base:
    image: ubuntu
    tag: "22.04"
  plugins: []
  source:
    path: .
    workdir: /app
  build:
    entrypoint: ["./run.sh"]
    env:
      TZ: Asia/Seoul
    expose: [8080]
  push:
    registry: harbor.example.local
    project: sdx
    deploy:
      enabled: false
`

func TestParseAndValidateOK(t *testing.T) {
	spec, err := parseBuildSpec([]byte(sampleBuildYAML))
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if err := spec.Validate(""); err != nil {
		t.Fatalf("validate: %v", err)
	}
	if got, want := spec.ImageRef(), "harbor.example.local/sdx/my-app:1.0.0"; got != want {
		t.Errorf("ImageRef = %q, want %q", got, want)
	}
	if got, want := spec.BaseRef(""), "ubuntu:22.04"; got != want {
		t.Errorf("BaseRef = %q, want %q", got, want)
	}
}

func TestParseRejectsUnknownField(t *testing.T) {
	bad := strings.Replace(sampleBuildYAML, "kind: ImageBuild", "kind: ImageBuild\nbogus: 1", 1)
	if _, err := parseBuildSpec([]byte(bad)); err == nil {
		t.Fatal("expected error for unknown field")
	}
}

func TestValidateRejectsBadInput(t *testing.T) {
	spec, err := parseBuildSpec([]byte(sampleBuildYAML))
	if err != nil {
		t.Fatal(err)
	}
	spec.Spec.Base.Image = "evil"    // allowlist 위반
	spec.Metadata.Name = "My App"    // 이름 규칙 위반
	spec.Spec.Source.Path = "../etc" // 경로 탈출
	spec.Spec.Build.Env = map[string]string{"1BAD": "x"}
	err = spec.Validate("")
	if err == nil {
		t.Fatal("expected validation error")
	}
	for _, want := range []string{"allowlist", "metadata.name", "source.path", "env key"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("error %q does not mention %q", err, want)
		}
	}
}

func TestRenderDockerfile(t *testing.T) {
	spec, err := parseBuildSpec([]byte(sampleBuildYAML))
	if err != nil {
		t.Fatal(err)
	}
	spec.Spec.Plugins = []PluginRef{{Name: "vacuum-lib", Version: "1.0.3"}}
	df, err := renderDockerfile(spec, spec.BaseRef(""))
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"FROM ubuntu:22.04",
		"COPY plugins/vacuum-lib/ /opt/plugins/vacuum-lib/",
		"WORKDIR /app",
		"COPY src/ /app/",
		`ENV TZ="Asia/Seoul"`,
		"EXPOSE 8080",
		`ENTRYPOINT ["./run.sh"]`,
	} {
		if !strings.Contains(df, want) {
			t.Errorf("Dockerfile missing %q:\n%s", want, df)
		}
	}
}

func TestExtractTarGzRejectsTraversal(t *testing.T) {
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gz)
	body := []byte("x")
	_ = tw.WriteHeader(&tar.Header{Name: "../escape.txt", Mode: 0o644, Size: int64(len(body)), Typeflag: tar.TypeReg})
	_, _ = tw.Write(body)
	tw.Close()
	gz.Close()

	dst := t.TempDir()
	if err := extractTarGz(&buf, dst, 1<<20); err == nil {
		t.Fatal("expected path traversal to be rejected")
	}
	if _, err := os.Stat(filepath.Join(filepath.Dir(dst), "escape.txt")); err == nil {
		t.Fatal("file escaped the destination directory")
	}
}
