// gRPC 기반 API
package server

import (
	"fmt"
	"os"
	"reflect"

	"github.com/go-pg/pg/v10/orm"
	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	_ "gitlab.suredatalab.kr/services/metadata"
	"google.golang.org/grpc"

	"gitlab.suredatalab.kr/beymons/devices"
)

// DeviceServer - Microservice를 위한 타입
type DevicesServer struct {
	devices.DevicesServer
	devices.SensorTypesServer
	devices.DeviceConfigsServer
}

var (
	rootcaKey   string
	requiredEnv = []string{}
)

//	func SampleDecoder(v reflect.Value, data map[string]interface{}) error {
//		value := &Sample{}
//		// 사용자 정의 타입 처리
//		v.Set(reflect.Indirect(reflect.ValueOf(value)))
//		return nil
//	}

// Init - 서비스 초기화
func (s *DevicesServer) Init() {
	// 환경변수 확인
	for _, name := range requiredEnv {
		if len(os.Getenv(name)) == 0 {
			log.Fatalf("Environment %q is not set", name)
		}
	}

	if _, err := pgorm.ConnectDB(); err != nil {
		log.Fatalf("DB connection failed: %v", err)
	}

	cert := os.Getenv("MQTT_CERT")
	if len(cert) == 0 {
		cert = "/cert/root-CA.crt"
	}

	createScheme()

	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	query := conn.Model()
	query.Model((*devices.Device)(nil)).Column("device_id").Group("device_id")
	query.Join("JOIN device_histories USING (device_id)")

	if pgorm.ExistTable(conn, "user_entity") {
		query.Join("LEFT JOIN user_entity").JoinOn("created_user_id = user_entity.id")
	}
	query.ColumnExpr("MAX(created_at) FILTER (WHERE action = ?) created_at", devices.DeviceHistory_CREATE)
	query.ColumnExpr("LAST(created_user_id, created_at) FILTER (WHERE action = ?) created_user_id", devices.DeviceHistory_CREATE)
	query.ColumnExpr("LAST(created_name, created_at) FILTER (WHERE action = ?) created_name", devices.DeviceHistory_CREATE)
	query.ColumnExpr("MAX(created_at) FILTER (WHERE action <> ?) updated_at", devices.DeviceHistory_STATUS)
	query.ColumnExpr("LAST(created_user_id, created_at) FILTER (WHERE action <> ?) updated_user_id", devices.DeviceHistory_STATUS)
	query.ColumnExpr("LAST(created_name, created_at) FILTER (WHERE action <> ?) updated_name", devices.DeviceHistory_STATUS)

	queries := []string{
		fmt.Sprintf("CREATE MATERIALIZED VIEW IF NOT EXISTS view_device_summary AS %s", orm.NewSelectQuery(query).String()),
		"CREATE UNIQUE INDEX IF NOT EXISTS view_device_status_summary_key ON view_device_summary USING BTREE (device_id ASC NULLS FIRST)",
	}

	for i, query := range queries {
		if _, err := conn.Exec(query); err != nil {
			log.Errorf("Failed to exec[%d] query: %s", i, err.Error())
		}
	}

	// 권한 등록
	if err := Register(); err != nil {
		log.Error(err)
	}

	// 서비스 계정으로 인증
	ctx, err := auth.ServiceAccount()
	if err != nil {
		log.Error("Failed to sign-in service account", "error", err)
	}

	// 알림 템플릿 등록
	registerMsgTemplate(ctx)

	// JSON -> devices.Sensor
	pgorm.RegisterDecoder(devices.Sensor{}, func(v reflect.Value, data map[string]any) error {
		value := &devices.Sensor{
			SensorId:   fmt.Sprint(data["sensor_id"]),
			DeviceId:   fmt.Sprint(data["device_id"]),
			ChannelId:  uint32(data["channel_id"].(float64)),
			SensorType: fmt.Sprint(data["sensor_type"]),
			Status:     devices.DeviceStatus(devices.DeviceStatus_value[fmt.Sprint(data["status"])]),
		}
		if v, ok := data["display_name"]; ok && v != nil {
			value.DisplayName = fmt.Sprint(v)
		}
		if v, ok := data["description"]; ok && v != nil {
			value.Description = fmt.Sprint(v)
		}
		if v, ok := data["probes"]; ok && v != nil {
			value.Probes = uint32(v.(float64))
		}

		v.Set(reflect.Indirect(reflect.ValueOf(value)))
		return nil
	})
}

// Prune - 서비스에서 사용한 테이블 정리
func (s *DevicesServer) Prune() error {
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
	srv := DevicesServer{}
	srv.Init()
	addr, serve := sdlmicro.NewTestServer(func(g *grpc.Server) {
		devices.RegisterDevicesServer(g, srv)
		devices.RegisterSensorTypesServer(g, srv)
		devices.RegisterDeviceConfigsServer(g, srv)
	})
	go serve()
	return addr
}
