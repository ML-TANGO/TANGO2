package main

// build_api.go: 빌드 요청(업로드) REST API + 빌드 메트릭 (DEV_PLAN 2장, 5장, 6장)
//
// 엔드포인트
//   POST /builds            소스(tar.gz) + build.yaml 업로드 → 202 + 작업 ID
//   GET  /builds            작업 목록
//   GET  /builds/:id        작업 상태
//   GET  /builds/:id/logs   빌드/Push/배포 로그
//
// 환경변수
//   BUILD_TOKEN          설정 시 /builds 요청에 "Authorization: Bearer <token>" 필요
//   BUILD_DATA_DIR       작업 저장 경로 (기본 data/builds)
//   BUILD_PLUGIN_ROOT    플러그인 저장소 로컬 경로 (기본 data/plugins, D1 결정 전 임시)
//   BUILD_BASE_PREFIX    베이스 이미지 레지스트리 접두어 (예: harbor.example.local/proxy)
//   BUILD_MAX_CONCURRENT 동시 빌드 수 (기본 2)
//   BUILD_TIMEOUT_MIN    작업당 제한 시간(분) (기본 30)
//   BUILD_MAX_UPLOAD_MB  업로드 최대 크기(MB) (기본 500)
//   HARBOR_USER / HARBOR_PASSWORD  레지스트리 자격증명 (평문 설정 파일에 두지 않는다)
//   DOCKER_HOST          빌드를 수행할 Docker 데몬 (기본 로컬 소켓)

import (
	"crypto/subtle"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/docker/docker/client"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
)

var buildJobs = prometheus.NewCounterVec(
	prometheus.CounterOpts{
		Name: "sdx_build_jobs_total",
		Help: "Finished image build jobs by final status",
	},
	[]string{"status"},
)

var buildDuration = prometheus.NewHistogram(
	prometheus.HistogramOpts{
		Name:    "sdx_build_duration_seconds",
		Help:    "Image build job duration (build + push + deploy)",
		Buckets: prometheus.ExponentialBuckets(10, 2, 8),
	},
)

type buildAPI struct {
	store          *jobStore
	runner         *builder
	dataDir        string
	pluginRoot     string
	maxUploadBytes int64
	token          string
}

// registerBuildRoutes: 빌드 API 라우트 등록. main()에서 r.Run 전에 호출한다.
func registerBuildRoutes(r *gin.Engine, inv *Inventory) {
	dockerCli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		log.Fatalf("[build] docker client: %v", err)
	}

	maxMB, _ := strconv.Atoi(getenv("BUILD_MAX_UPLOAD_MB", "500"))
	maxConc, _ := strconv.Atoi(getenv("BUILD_MAX_CONCURRENT", "2"))
	timeoutMin, _ := strconv.Atoi(getenv("BUILD_TIMEOUT_MIN", "30"))
	if maxConc < 1 {
		maxConc = 1
	}

	api := &buildAPI{
		store:      newJobStore(),
		dataDir:    getenv("BUILD_DATA_DIR", "data/builds"),
		pluginRoot: getenv("BUILD_PLUGIN_ROOT", "data/plugins"),
		token:      os.Getenv("BUILD_TOKEN"),
		runner: &builder{
			inv:        inv,
			docker:     dockerCli,
			pluginRoot: getenv("BUILD_PLUGIN_ROOT", "data/plugins"),
			basePrefix: os.Getenv("BUILD_BASE_PREFIX"),
			regUser:    os.Getenv("HARBOR_USER"),
			regPass:    os.Getenv("HARBOR_PASSWORD"),
			timeout:    time.Duration(timeoutMin) * time.Minute,
			maxUpload:  int64(maxMB) << 20,
			sem:        make(chan struct{}, maxConc),
		},
	}
	api.maxUploadBytes = int64(maxMB) << 20

	if api.token == "" {
		log.Printf("[build] BUILD_TOKEN not set: /builds API is unauthenticated")
	}
	prometheus.MustRegister(buildJobs, buildDuration)

	g := r.Group("/builds", api.authMiddleware())
	g.POST("", api.submit)
	g.GET("", api.list)
	g.GET("/:id", api.get)
	g.GET("/:id/logs", api.logs)
	log.Printf("[build] routes registered (data=%s, plugins=%s, max_concurrent=%d)", api.dataDir, api.pluginRoot, maxConc)
}

func (a *buildAPI) authMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if a.token == "" {
			c.Next()
			return
		}
		want := "Bearer " + a.token
		if subtle.ConstantTimeCompare([]byte(c.GetHeader("Authorization")), []byte(want)) != 1 {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
			return
		}
		c.Next()
	}
}

// submit: POST /builds (multipart: source=tar.gz, config=build.yaml)
func (a *buildAPI) submit(c *gin.Context) {
	c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, a.maxUploadBytes)

	cfgHeader, err := c.FormFile("config")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "config (build.yaml) file required"})
		return
	}
	cfgFile, err := cfgHeader.Open()
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	cfgData, err := io.ReadAll(io.LimitReader(cfgFile, maxBuildYAMLLen+1))
	cfgFile.Close()
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	spec, err := parseBuildSpec(cfgData)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if err := spec.Validate(a.runner.pluginRoot); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	srcHeader, err := c.FormFile("source")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "source (tar.gz) file required"})
		return
	}

	id, err := newJobID()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	dir, err := jobDir(a.dataDir, id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := c.SaveUploadedFile(srcHeader, filepath.Join(dir, "source.tar.gz")); err != nil {
		_ = os.RemoveAll(dir)
		c.JSON(http.StatusBadRequest, gin.H{"error": "save source: " + err.Error()})
		return
	}
	if err := os.WriteFile(filepath.Join(dir, "build.yaml"), cfgData, 0o644); err != nil {
		_ = os.RemoveAll(dir)
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	job := newJob(id, spec, dir)
	a.store.Add(job)
	go a.runner.Run(job)

	c.JSON(http.StatusAccepted, job.View())
}

// list: GET /builds
func (a *buildAPI) list(c *gin.Context) {
	c.JSON(http.StatusOK, a.store.List())
}

// get: GET /builds/:id
func (a *buildAPI) get(c *gin.Context) {
	job, ok := a.store.Get(c.Param("id"))
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "build not found"})
		return
	}
	c.JSON(http.StatusOK, job.View())
}

// logs: GET /builds/:id/logs
func (a *buildAPI) logs(c *gin.Context) {
	job, ok := a.store.Get(c.Param("id"))
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "build not found"})
		return
	}
	c.Data(http.StatusOK, "text/plain; charset=utf-8", job.Logs())
}
