package main

// build_job.go: 빌드 작업 상태/로그 저장소, ImageMaker(빌드) + ImagePusher(Push, 배포 트리거) 파이프라인
// (DEV_PLAN 3장, 4장)

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"sync"
	"time"

	"github.com/docker/docker/api/types/build"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/api/types/registry"
	"github.com/docker/docker/client"
)

// 작업 상태 (DEV_PLAN 4.3: queued → building → pushing → deploying → succeeded | failed)
const (
	jobQueued    = "queued"
	jobBuilding  = "building"
	jobPushing   = "pushing"
	jobDeploying = "deploying"
	jobSucceeded = "succeeded"
	jobFailed    = "failed"
)

var digestRe = regexp.MustCompile(`digest: (sha256:[0-9a-f]{64})`)

// JobView: API 응답용 스냅샷 (로그 제외)
type JobView struct {
	ID        string         `json:"id"`
	Name      string         `json:"name"`
	Image     string         `json:"image"`
	Status    string         `json:"status"`
	Error     string         `json:"error,omitempty"`
	Digest    string         `json:"digest,omitempty"`
	Deploy    []DeployResult `json:"deploy,omitempty"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
}

type DeployResult struct {
	Node        string `json:"node"`
	Status      string `json:"status"` // succeeded | failed
	ContainerID string `json:"container_id,omitempty"`
	Error       string `json:"error,omitempty"`
}

// Job: 빌드 작업 1건. io.Writer로 동작해 Docker 빌드/Push 로그를 그대로 받는다.
type Job struct {
	mu        sync.Mutex
	id        string
	spec      *BuildSpec
	dir       string // 작업 디렉토리: source.tar.gz, build.yaml, context/
	status    string
	errMsg    string
	digest    string
	deploy    []DeployResult
	logBuf    bytes.Buffer
	createdAt time.Time
	updatedAt time.Time
}

func newJob(id string, spec *BuildSpec, dir string) *Job {
	now := time.Now()
	return &Job{id: id, spec: spec, dir: dir, status: jobQueued, createdAt: now, updatedAt: now}
}

// Write: io.Writer 구현 (로그 누적)
func (j *Job) Write(p []byte) (int, error) {
	j.mu.Lock()
	defer j.mu.Unlock()
	j.updatedAt = time.Now()
	return j.logBuf.Write(p)
}

func (j *Job) logf(format string, a ...any) {
	fmt.Fprintf(j, "[%s] "+format+"\n", append([]any{time.Now().Format(time.RFC3339)}, a...)...)
}

func (j *Job) setStatus(s string) {
	j.mu.Lock()
	defer j.mu.Unlock()
	j.status = s
	j.updatedAt = time.Now()
}

func (j *Job) setDigest(d string) {
	j.mu.Lock()
	defer j.mu.Unlock()
	j.digest = d
}

func (j *Job) addDeploy(r DeployResult) {
	j.mu.Lock()
	defer j.mu.Unlock()
	j.deploy = append(j.deploy, r)
}

// finish: 최종 상태 기록. 기록된 상태를 반환한다.
func (j *Job) finish(err error) string {
	j.mu.Lock()
	defer j.mu.Unlock()
	if err != nil {
		j.status = jobFailed
		j.errMsg = err.Error()
	} else {
		j.status = jobSucceeded
	}
	j.updatedAt = time.Now()
	return j.status
}

func (j *Job) View() JobView {
	j.mu.Lock()
	defer j.mu.Unlock()
	deploy := make([]DeployResult, len(j.deploy))
	copy(deploy, j.deploy)
	return JobView{
		ID: j.id, Name: j.spec.Metadata.Name, Image: j.spec.ImageRef(),
		Status: j.status, Error: j.errMsg, Digest: j.digest, Deploy: deploy,
		CreatedAt: j.createdAt, UpdatedAt: j.updatedAt,
	}
}

func (j *Job) Logs() []byte {
	j.mu.Lock()
	defer j.mu.Unlock()
	return append([]byte(nil), j.logBuf.Bytes()...)
}

// jobStore: 메모리 기반 작업 저장소 (DEV_PLAN D5: 초기 구현)
type jobStore struct {
	mu   sync.RWMutex
	jobs map[string]*Job
}

func newJobStore() *jobStore {
	return &jobStore{jobs: map[string]*Job{}}
}

func (s *jobStore) Add(j *Job) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.jobs[j.id] = j
}

func (s *jobStore) Get(id string) (*Job, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	j, ok := s.jobs[id]
	return j, ok
}

func (s *jobStore) List() []JobView {
	s.mu.RLock()
	jobs := make([]*Job, 0, len(s.jobs))
	for _, j := range s.jobs {
		jobs = append(jobs, j)
	}
	s.mu.RUnlock()

	views := make([]JobView, 0, len(jobs))
	for _, j := range jobs {
		views = append(views, j.View())
	}
	sort.Slice(views, func(a, b int) bool { return views[a].CreatedAt.After(views[b].CreatedAt) })
	return views
}

// builder: 빌드 실행기. 동시 실행 수는 sem으로 제한한다 (DEV_PLAN 8 리스크 대응).
type builder struct {
	inv        *Inventory
	docker     *client.Client // 빌드를 수행하는 Docker 데몬 (DOCKER_HOST 환경변수 기준)
	pluginRoot string
	basePrefix string
	regUser    string
	regPass    string
	timeout    time.Duration
	maxUpload  int64
	sem        chan struct{}
}

// Run: 작업을 동기적으로 실행한다. 호출자는 goroutine으로 감싸서 사용한다.
func (b *builder) Run(j *Job) {
	b.sem <- struct{}{}
	defer func() { <-b.sem }()

	ctx, cancel := context.WithTimeout(context.Background(), b.timeout)
	defer cancel()

	j.logf("job %s started (image %s)", j.id, j.spec.ImageRef())
	start := time.Now()
	err := b.execute(ctx, j)
	status := j.finish(err)
	if err != nil {
		j.logf("job failed: %v", err)
	} else {
		j.logf("job succeeded")
	}
	buildJobs.WithLabelValues(status).Inc()
	buildDuration.Observe(time.Since(start).Seconds())
}

// execute: ImageMaker → ImagePusher 순서로 실행
func (b *builder) execute(ctx context.Context, j *Job) error {
	spec := j.spec
	ctxDir := filepath.Join(j.dir, "context")

	// ── ImageMaker ──
	j.setStatus(jobBuilding)
	j.logf("preparing build context")
	archive := filepath.Join(j.dir, "source.tar.gz")
	if err := prepareContext(ctxDir, j.dir, archive, spec, b.pluginRoot, b.maxUpload); err != nil {
		return fmt.Errorf("prepare context: %w", err)
	}

	baseRef := spec.BaseRef(b.basePrefix)
	if err := b.ensureBaseImage(ctx, j, baseRef); err != nil {
		return err
	}

	dockerfile, err := renderDockerfile(spec, baseRef)
	if err != nil {
		return fmt.Errorf("render Dockerfile: %w", err)
	}
	if err := os.WriteFile(filepath.Join(ctxDir, "Dockerfile"), []byte(dockerfile), 0o644); err != nil {
		return err
	}
	j.logf("generated Dockerfile:\n%s", dockerfile)

	tarPath := filepath.Join(j.dir, "context.tar")
	if err := writeContextTar(ctxDir, tarPath); err != nil {
		return fmt.Errorf("pack build context: %w", err)
	}

	ref := spec.ImageRef()
	if err := b.buildImage(ctx, j, tarPath, ref); err != nil {
		return err
	}

	// ── ImagePusher ──
	j.setStatus(jobPushing)
	auth, err := registryAuth(spec.Spec.Push.Registry, b.regUser, b.regPass)
	if err != nil {
		return err
	}
	j.logf("pushing %s", ref)
	rc, err := b.docker.ImagePush(ctx, ref, image.PushOptions{RegistryAuth: auth})
	if err != nil {
		return fmt.Errorf("push: %w", err)
	}
	digest, err := consumeDockerStream(rc, j)
	rc.Close()
	if err != nil {
		return fmt.Errorf("push: %w", err)
	}
	j.setDigest(digest)
	j.logf("pushed %s (digest %s)", ref, digest)

	if !spec.Spec.Push.Deploy.Enabled {
		return nil
	}

	// ── 배포 트리거 (1차년도 시스템: 노드별 pull → create → start) ──
	j.setStatus(jobDeploying)
	failed := false
	for _, node := range spec.Spec.Push.Deploy.Nodes {
		res := b.deployNode(ctx, node, ref, spec, auth)
		j.addDeploy(res)
		j.logf("deploy on %s: %s", node, res.Status)
		if res.Status == jobFailed {
			failed = true
		}
	}
	if failed {
		return errors.New("deploy failed on one or more nodes")
	}
	return nil
}

// ensureBaseImage: 로컬에 없으면 베이스 이미지를 Pull (DEV_PLAN 3.1)
func (b *builder) ensureBaseImage(ctx context.Context, j *Job, ref string) error {
	if _, err := b.docker.ImageInspect(ctx, ref); err == nil {
		j.logf("base image %s found locally", ref)
		return nil
	}
	j.logf("pulling base image %s", ref)
	rc, err := b.docker.ImagePull(ctx, ref, image.PullOptions{})
	if err != nil {
		return fmt.Errorf("pull base image: %w", err)
	}
	defer rc.Close()
	if _, err := consumeDockerStream(rc, j); err != nil {
		return fmt.Errorf("pull base image: %w", err)
	}
	return nil
}

// buildImage: Docker 데몬으로 이미지 빌드 후 로그 수집 (DEV_PLAN 3.4)
func (b *builder) buildImage(ctx context.Context, j *Job, tarPath, ref string) error {
	f, err := os.Open(tarPath)
	if err != nil {
		return err
	}
	defer f.Close()

	j.logf("building image %s", ref)
	resp, err := b.docker.ImageBuild(ctx, f, build.ImageBuildOptions{
		Tags:        []string{ref},
		Dockerfile:  "Dockerfile",
		Remove:      true,
		ForceRemove: true,
	})
	if err != nil {
		return fmt.Errorf("build: %w", err)
	}
	defer resp.Body.Close()
	if _, err := consumeDockerStream(resp.Body, j); err != nil {
		return fmt.Errorf("build: %w", err)
	}
	return nil
}

// deployNode: 대상 노드에서 pull → (기존 동명 컨테이너 제거) → create → start
func (b *builder) deployNode(ctx context.Context, nodeName, ref string, spec *BuildSpec, auth string) DeployResult {
	res := DeployResult{Node: nodeName, Status: jobFailed}
	fail := func(err error) DeployResult {
		res.Error = err.Error()
		return res
	}

	ns, ok := b.inv.Nodes[nodeName]
	if !ok {
		return fail(fmt.Errorf("unknown node %q", nodeName))
	}
	cli, err := newDockerClient(ns)
	if err != nil {
		return fail(err)
	}
	defer cli.Close()

	nctx, cancel := context.WithTimeout(ctx, timeoutOf(ns))
	defer cancel()

	rc, err := cli.ImagePull(nctx, ref, image.PullOptions{RegistryAuth: auth})
	if err != nil {
		return fail(fmt.Errorf("pull: %w", err))
	}
	_, _ = io.Copy(io.Discard, rc)
	rc.Close()

	name := spec.Metadata.Name
	// 재배포: 같은 이름의 컨테이너가 있으면 제거 (없으면 에러는 무시)
	_ = cli.ContainerRemove(nctx, name, container.RemoveOptions{Force: true})

	cfg, hostCfg, err := toConfigs(ref, spec.Spec.Push.Deploy.Ports)
	if err != nil {
		return fail(err)
	}
	created, err := cli.ContainerCreate(nctx, cfg, hostCfg, nil, nil, name)
	if err != nil {
		return fail(fmt.Errorf("create: %w", err))
	}
	if err := cli.ContainerStart(nctx, name, container.StartOptions{}); err != nil {
		return fail(fmt.Errorf("start: %w", err))
	}

	res.Status = jobSucceeded
	res.ContainerID = created.ID
	return res
}

// ───────────── helpers ─────────────

// dockerMsg: Docker 빌드/Push/Pull 스트림의 JSON 메시지
type dockerMsg struct {
	Stream      string `json:"stream"`
	Status      string `json:"status"`
	Error       string `json:"error"`
	ErrorDetail struct {
		Message string `json:"message"`
	} `json:"errorDetail"`
}

// consumeDockerStream: JSON 스트림을 읽어 w에 기록하고, 오류 메시지가 있으면 에러로 반환한다.
// push 결과의 digest도 함께 반환한다.
func consumeDockerStream(r io.Reader, w io.Writer) (string, error) {
	dec := json.NewDecoder(r)
	digest := ""
	for {
		var m dockerMsg
		err := dec.Decode(&m)
		if err == io.EOF {
			return digest, nil
		}
		if err != nil {
			return digest, err
		}
		if m.Error != "" || m.ErrorDetail.Message != "" {
			msg := m.Error
			if msg == "" {
				msg = m.ErrorDetail.Message
			}
			return digest, errors.New(msg)
		}
		if m.Stream != "" {
			_, _ = io.WriteString(w, m.Stream)
		}
		if m.Status != "" {
			_, _ = fmt.Fprintln(w, m.Status)
			if sub := digestRe.FindStringSubmatch(m.Status); sub != nil {
				digest = sub[1]
			}
		}
	}
}

// writeContextTar: 빌드 컨텍스트 디렉토리를 tar 파일로 저장
func writeContextTar(dir, tarPath string) error {
	f, err := os.Create(tarPath)
	if err != nil {
		return err
	}
	defer f.Close()
	return tarDirectory(dir, f)
}

// registryAuth: Docker RegistryAuth 헤더 값 (base64url JSON)
func registryAuth(server, user, pass string) (string, error) {
	if user == "" {
		return "", nil // 공개 레지스트리 또는 노드 측 docker login 사용
	}
	b, err := json.Marshal(registry.AuthConfig{Username: user, Password: pass, ServerAddress: server})
	if err != nil {
		return "", err
	}
	return base64.URLEncoding.EncodeToString(b), nil
}

func newJobID() (string, error) {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

// jobDir: 작업 디렉토리 생성
func jobDir(root, id string) (string, error) {
	dir := filepath.Join(root, id)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	return dir, nil
}
