// gRPC 기반 API
package server

import (
	"context"
	"os"

	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc"

	"gitlab.suredatalab.kr/beymons/collects"
)

// CollectServer - Microservice를 위한 타입
type CollectsServer struct {
	collects.CollectsServer
}

var (
	serviceAccountID = "00000000-0000-0000-0000-000000000000"
	requiredEnv      = []string{}
)

// Init - 서비스 초기화
func (s *CollectsServer) Init() {
	// 환경변수 확인
	for _, name := range requiredEnv {
		if len(os.Getenv(name)) == 0 {
			log.Fatalf("Environment %q is not set", name)
		}
	}

	if _, err := pgorm.ConnectDB(); err != nil {
		log.Fatalf("DB connection failed: %v", err)
	}

	createScheme()

	// 권한 등록
	if err := Register(); err != nil {
		log.Error(err.Error())
	}

	// 서비스 계정
	var ctx context.Context
	if os.Getenv("SECURE_MODE") != "disable" {
		var err error
		if ctx, err = auth.ServiceAccount(); err == nil {
			if claims, err := auth.GetClaim(ctx); err == nil {
				serviceAccountID = claims.UserID
			}
		}
	} else {
		ctx = context.Background()
	}

	registerMsgTemplate(ctx)

	// 이벤트 기록을 위한 스트림 생성
	if _, err := async.CreateStream(collects.PACKAGE_NAME, 100000); err != nil {
		log.Error("Failed to create stream", "error", err)
	}
}

// AuthFuncOverride is a function that performs self-authentication instead of the global `AuthFunc`.
// func (s *CollectsServer) AuthFuncOverride(ctx context.Context, fullMethodName string) (context.Context, error) {}

// Prune - 서비스에서 사용한 테이블 정리
func (s *CollectsServer) Prune() error {
	if err := deleteScheme(); err != nil {
		log.Error(err.Error())
	}

	// 권한 제거
	if err := Deregister(); err != nil {
		log.Error(err.Error())
	}

	return nil
}

// TestServer
func TestServer() string {
	srv := CollectsServer{}
	srv.Init()
	addr, serve := sdlmicro.NewTestServer(func(g *grpc.Server) {
		collects.RegisterCollectsServer(g, srv)
	})
	go serve()
	return addr
}
