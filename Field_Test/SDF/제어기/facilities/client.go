package facilities

import (
	"os"
	"sync"

	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"google.golang.org/grpc"
)

const PACKAGE_NAME = "facilities"

var (
	cm             = &sync.Mutex{}
	client         *ServiceClient
	defaultAddress = "facilities:50251"
)

type ServiceClient struct {
	FacilitiesClient
	ProductsClient
}

func newClient(conn grpc.ClientConnInterface) *ServiceClient {
	return &ServiceClient{
		NewFacilitiesClient(conn),
		NewProductsClient(conn),
	}
}

// Client 함수는 facilities 서비스에 연결하기 위한 client를 리턴하는 함수이다.
func Client() *ServiceClient {
	cm.Lock()
	defer cm.Unlock()

	if client != nil {
		return client
	}

	serviceAddress := os.Getenv("FACILITIES_SERVICE")
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

	client = newClient(conn)
	return client
}

// TestClient 함수는 테스트를 위한 서버를 생성하고 client를 리턴하는 함수이다.
func TestClient(addr string) *ServiceClient {
	client = newClient(sdlmicro.TestConn(addr))
	return client
}
