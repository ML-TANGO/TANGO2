// @FIXME: Summary
//
// @FIXME: Description
package collects

import (
	"os"
	"sync"

	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"google.golang.org/grpc"
)

const PACKAGE_NAME = "collects"

var (
	cm             = &sync.Mutex{}
	client         CollectsClient
	defaultAddress = "collects:50251"
)

func Client() CollectsClient {
	cm.Lock()
	defer cm.Unlock()

	if client != nil {
		return client
	}

	serviceAddress := os.Getenv("COLLECTS_SERVICE")
	if len(serviceAddress) == 0 {
		serviceAddress = defaultAddress
	}

	// We don't need to error here, as this creates a pool and connections
	// will happen later
	conn, _ := grpc.Dial(
		serviceAddress,
		grpc.WithInsecure(),
		grpc.WithChainUnaryInterceptor(
			sdlmicro.ContextClientInterceptor(),
			otelgrpc.UnaryClientInterceptor(),
		),
		grpc.WithChainStreamInterceptor(
			sdlmicro.ContextClientStreamInterceptor(),
			otelgrpc.StreamClientInterceptor(),
		))

	client = NewCollectsClient(conn)
	return client
}

// TestClient 함수는 테스트를 위한 서버를 생성하고 client를 리턴하는 함수이다.
func TestClient(addr string) CollectsClient {
	client = NewCollectsClient(sdlmicro.TestConn(addr))
	return client
}
