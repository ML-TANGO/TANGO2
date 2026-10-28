package main

// build_spec.go: build.yaml 스키마, 검증, Dockerfile 생성, 빌드 컨텍스트 준비 (DEV_PLAN 2.2, 2.3, 3.3)

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"text/template"

	"gopkg.in/yaml.v3"
)

const (
	buildAPIVersion = "sdx/v1"
	buildKind       = "ImageBuild"
	maxBuildYAMLLen = 1 << 20 // build.yaml은 1MB까지만 허용
)

// allowedBaseImages: 베이스 이미지 허용 목록 (DEV_PLAN 2.3, D2 결정 전 기본값)
var allowedBaseImages = map[string]bool{
	"ubuntu":     true,
	"centos":     true,
	"debian":     true,
	"alpine":     true,
	"rockylinux": true,
}

var (
	nameRe    = regexp.MustCompile(`^[a-z0-9]+(?:[._-][a-z0-9]+)*$`)
	tagRe     = regexp.MustCompile(`^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$`)
	envKeyRe  = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)
	versionRe = regexp.MustCompile(`^[A-Za-z0-9_.+-]{1,64}$`)
)

// BuildSpec: build.yaml 구조 (DEV_PLAN 2.2)
type BuildSpec struct {
	APIVersion string      `yaml:"apiVersion"`
	Kind       string      `yaml:"kind"`
	Metadata   BuildMeta   `yaml:"metadata"`
	Spec       BuildDetail `yaml:"spec"`
}

type BuildMeta struct {
	Name string `yaml:"name"`
	Tag  string `yaml:"tag"`
}

type BuildDetail struct {
	Base    BaseImage    `yaml:"base"`
	Plugins []PluginRef  `yaml:"plugins"`
	Source  SourceSpec   `yaml:"source"`
	Build   BuildOptions `yaml:"build"`
	Push    PushSpec     `yaml:"push"`
}

type BaseImage struct {
	Image string `yaml:"image"`
	Tag   string `yaml:"tag"`
}

type PluginRef struct {
	Name    string `yaml:"name"`
	Version string `yaml:"version"`
}

type SourceSpec struct {
	Path    string `yaml:"path"`    // 아카이브 내 소스 경로
	Workdir string `yaml:"workdir"` // 컨테이너 내 작업 디렉토리
}

type BuildOptions struct {
	Entrypoint []string          `yaml:"entrypoint"`
	Env        map[string]string `yaml:"env"`
	Expose     []int             `yaml:"expose"`
}

type PushSpec struct {
	Registry string     `yaml:"registry"`
	Project  string     `yaml:"project"`
	Deploy   DeploySpec `yaml:"deploy"`
}

type DeploySpec struct {
	Enabled bool     `yaml:"enabled"`
	Nodes   []string `yaml:"nodes"`
	Ports   []string `yaml:"ports"` // e.g. ["8080:80"]
}

// parseBuildSpec: 알 수 없는 필드는 오류로 처리해 오타를 조기에 잡는다.
func parseBuildSpec(data []byte) (*BuildSpec, error) {
	if len(data) > maxBuildYAMLLen {
		return nil, fmt.Errorf("build.yaml too large")
	}
	var s BuildSpec
	dec := yaml.NewDecoder(bytes.NewReader(data))
	dec.KnownFields(true)
	if err := dec.Decode(&s); err != nil {
		return nil, fmt.Errorf("parse build.yaml: %w", err)
	}
	return &s, nil
}

// Validate: 요청 검증 (DEV_PLAN 2.3). pluginRoot 아래에 플러그인 디렉토리가 있는지도 확인한다.
func (s *BuildSpec) Validate(pluginRoot string) error {
	var errs []string
	add := func(format string, a ...any) { errs = append(errs, fmt.Sprintf(format, a...)) }

	if s.APIVersion != buildAPIVersion {
		add("apiVersion must be %q", buildAPIVersion)
	}
	if s.Kind != buildKind {
		add("kind must be %q", buildKind)
	}

	if !nameRe.MatchString(s.Metadata.Name) {
		add("metadata.name %q: lowercase letters, digits, '.', '_', '-' only", s.Metadata.Name)
	}
	if !tagRe.MatchString(s.Metadata.Tag) {
		add("metadata.tag %q: invalid image tag", s.Metadata.Tag)
	}

	if !allowedBaseImages[s.Spec.Base.Image] {
		add("spec.base.image %q is not in the allowlist", s.Spec.Base.Image)
	}
	if !tagRe.MatchString(s.Spec.Base.Tag) {
		add("spec.base.tag %q: invalid tag", s.Spec.Base.Tag)
	}

	for i, p := range s.Spec.Plugins {
		if !nameRe.MatchString(p.Name) {
			add("spec.plugins[%d].name %q: invalid", i, p.Name)
			continue
		}
		if !versionRe.MatchString(p.Version) {
			add("spec.plugins[%d].version %q: invalid", i, p.Version)
			continue
		}
		if pluginRoot != "" {
			if fi, err := os.Stat(pluginDir(pluginRoot, p)); err != nil || !fi.IsDir() {
				add("plugin %s@%s not found in plugin repository", p.Name, p.Version)
			}
		}
	}

	if !filepath.IsLocal(s.Spec.Source.Path) {
		add("spec.source.path %q must be a relative path inside the archive", s.Spec.Source.Path)
	}
	if !path.IsAbs(s.Spec.Source.Workdir) || strings.Contains(s.Spec.Source.Workdir, "..") {
		add("spec.source.workdir %q must be an absolute path", s.Spec.Source.Workdir)
	}
	if len(s.Spec.Build.Entrypoint) == 0 {
		add("spec.build.entrypoint is required")
	}
	for k := range s.Spec.Build.Env {
		if !envKeyRe.MatchString(k) {
			add("spec.build.env key %q: invalid", k)
		}
	}
	for _, port := range s.Spec.Build.Expose {
		if port < 1 || port > 65535 {
			add("spec.build.expose %d: out of range", port)
		}
	}

	if s.Spec.Push.Registry == "" {
		add("spec.push.registry is required")
	}
	if !nameRe.MatchString(s.Spec.Push.Project) {
		add("spec.push.project %q: invalid", s.Spec.Push.Project)
	}
	if s.Spec.Push.Deploy.Enabled && len(s.Spec.Push.Deploy.Nodes) == 0 {
		add("spec.push.deploy.nodes is required when deploy is enabled")
	}

	if len(errs) > 0 {
		return errors.New(strings.Join(errs, "; "))
	}
	return nil
}

// BaseRef: 베이스 이미지 참조 (prefix는 BUILD_BASE_PREFIX, 예: Harbor 프록시 캐시)
func (s *BuildSpec) BaseRef(prefix string) string {
	ref := s.Spec.Base.Image + ":" + s.Spec.Base.Tag
	if prefix != "" {
		return strings.TrimRight(prefix, "/") + "/" + ref
	}
	return ref
}

// ImageRef: 최종 이미지 참조 harbor.example.local/sdx/my-app:1.0.0 (DEV_PLAN 1.3)
func (s *BuildSpec) ImageRef() string {
	return fmt.Sprintf("%s/%s/%s:%s",
		s.Spec.Push.Registry, s.Spec.Push.Project, s.Metadata.Name, s.Metadata.Tag)
}

func pluginDir(root string, p PluginRef) string {
	return filepath.Join(root, p.Name, p.Version)
}

// ───────────── Dockerfile 생성 (DEV_PLAN 3.3) ─────────────

const dockerfileTmpl = `# generated by sdx-remote build
FROM {{.Base}}
{{- range .Plugins}}
COPY plugins/{{.Name}}/ /opt/plugins/{{.Name}}/
{{- end}}
WORKDIR {{.Workdir}}
COPY src/ {{.Workdir}}/
{{- range .Env}}
ENV {{.Key}}={{.Value}}
{{- end}}
{{- range .Expose}}
EXPOSE {{.}}
{{- end}}
ENTRYPOINT {{.Entrypoint}}
`

type envPair struct {
	Key   string
	Value string
}

type dockerfileData struct {
	Base       string
	Plugins    []PluginRef
	Workdir    string
	Env        []envPair
	Expose     []int
	Entrypoint string
}

// renderDockerfile: 베이스 + 플러그인 + 소스 조합 Dockerfile 생성
func renderDockerfile(s *BuildSpec, baseRef string) (string, error) {
	keys := make([]string, 0, len(s.Spec.Build.Env))
	for k := range s.Spec.Build.Env {
		keys = append(keys, k)
	}
	sort.Strings(keys) // 결정적 출력을 위해 정렬

	env := make([]envPair, 0, len(keys))
	for _, k := range keys {
		v, _ := json.Marshal(s.Spec.Build.Env[k]) // JSON 문자열은 Dockerfile의 큰따옴표 값과 호환
		env = append(env, envPair{Key: k, Value: string(v)})
	}

	ep, err := json.Marshal(s.Spec.Build.Entrypoint)
	if err != nil {
		return "", err
	}

	tmpl := template.Must(template.New("Dockerfile").Parse(dockerfileTmpl))
	var buf bytes.Buffer
	err = tmpl.Execute(&buf, dockerfileData{
		Base:       baseRef,
		Plugins:    s.Spec.Plugins,
		Workdir:    s.Spec.Source.Workdir,
		Env:        env,
		Expose:     s.Spec.Build.Expose,
		Entrypoint: string(ep),
	})
	if err != nil {
		return "", err
	}
	return buf.String() + "\n", nil
}

// ───────────── 빌드 컨텍스트 준비 (소스 해제 + 플러그인 복사) ─────────────

// prepareContext: archive(tar.gz)를 jobDir/source에 풀고, ctxDir/src 와 ctxDir/plugins 를 구성한다.
func prepareContext(ctxDir, jobDir, archive string, s *BuildSpec, pluginRoot string, maxBytes int64) error {
	if err := os.RemoveAll(ctxDir); err != nil {
		return err
	}
	srcRoot := filepath.Join(jobDir, "source")
	if err := os.RemoveAll(srcRoot); err != nil {
		return err
	}

	f, err := os.Open(archive)
	if err != nil {
		return err
	}
	defer f.Close()
	if err := extractTarGz(f, srcRoot, maxBytes); err != nil {
		return fmt.Errorf("extract source: %w", err)
	}

	if err := copyTree(filepath.Join(srcRoot, s.Spec.Source.Path), filepath.Join(ctxDir, "src")); err != nil {
		return fmt.Errorf("copy source: %w", err)
	}
	for _, p := range s.Spec.Plugins {
		dst := filepath.Join(ctxDir, "plugins", p.Name)
		if err := copyTree(pluginDir(pluginRoot, p), dst); err != nil {
			return fmt.Errorf("copy plugin %s@%s: %w", p.Name, p.Version, err)
		}
	}
	return nil
}

// extractTarGz: 경로 탈출(zip-slip/tar-slip) 방지, 심볼릭 링크 거부, 전체 크기 제한 (DEV_PLAN 2.3)
func extractTarGz(r io.Reader, dst string, maxBytes int64) error {
	gz, err := gzip.NewReader(r)
	if err != nil {
		return fmt.Errorf("not a gzip archive: %w", err)
	}
	defer gz.Close()

	tr := tar.NewReader(gz)
	var total int64
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return err
		}
		name := filepath.Clean(filepath.FromSlash(hdr.Name))
		if !filepath.IsLocal(name) {
			return fmt.Errorf("unsafe path in archive: %q", hdr.Name)
		}
		target := filepath.Join(dst, name)

		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0o755); err != nil {
				return err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
				return err
			}
			out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, hdr.FileInfo().Mode().Perm()|0o600)
			if err != nil {
				return err
			}
			n, err := io.Copy(out, io.LimitReader(tr, maxBytes-total+1))
			out.Close()
			if err != nil {
				return err
			}
			total += n
			if total > maxBytes {
				return fmt.Errorf("archive exceeds %d bytes", maxBytes)
			}
		case tar.TypeXGlobalHeader:
			// 무시
		default:
			return fmt.Errorf("unsupported entry type %q for %s", hdr.Typeflag, hdr.Name)
		}
	}
}

// copyTree: src 디렉토리를 dst로 복사. 일반 파일과 디렉토리만 복사한다.
func copyTree(src, dst string) error {
	fi, err := os.Stat(src)
	if err != nil {
		return err
	}
	if !fi.IsDir() {
		return fmt.Errorf("%s is not a directory", src)
	}
	return filepath.WalkDir(src, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(src, p)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if d.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		if !d.Type().IsRegular() {
			return nil // 심볼릭 링크 등은 건너뜀
		}
		return copyFile(p, target)
	})
}

func copyFile(src, dst string) error {
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	info, err := in.Stat()
	if err != nil {
		return err
	}
	out, err := os.OpenFile(dst, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, info.Mode().Perm())
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}

// tarDirectory: 빌드 컨텍스트 디렉토리를 tar 스트림으로 기록 (Docker ImageBuild 입력)
func tarDirectory(dir string, w io.Writer) error {
	tw := tar.NewWriter(w)
	err := filepath.WalkDir(dir, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(dir, p)
		if err != nil {
			return err
		}
		if rel == "." {
			return nil
		}
		if !d.IsDir() && !d.Type().IsRegular() {
			return nil
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		hdr, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		hdr.Name = filepath.ToSlash(rel)
		if d.IsDir() {
			hdr.Name += "/"
		}
		if err := tw.WriteHeader(hdr); err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		in, err := os.Open(p)
		if err != nil {
			return err
		}
		defer in.Close()
		_, err = io.Copy(tw, in)
		return err
	})
	if err != nil {
		return err
	}
	return tw.Close()
}
