package server

import (
	"testing"

	"os"

	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"gitlab.suredatalab.kr/services/metadata"
	metaSrv "gitlab.suredatalab.kr/services/metadata/server"

	"gitlab.suredatalab.kr/beymons/devices"
)

const (
	TEST_SITE_ID     = "test_001"
	TEST_FACILITY_ID = "test_f01"
)

var (
	closeConsumer = make(chan bool, 1)
)

func TestMain(m *testing.M) {
	os.Setenv("SECURE_MODE", "disable")

	ensureTestSuite()
	code := m.Run()
	clearTestSuite()
	os.Exit(code)
}

func ensureTestSuite() {
	// 메타데이터 서비스 실행
	metadata.TestClient(metaSrv.TestServer())

	// 서비스 실행
	devices.TestClient(TestServer())
	go DeviceConsumer(closeConsumer)
}

func clearTestSuite() {
	closeConsumer <- true
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
}
