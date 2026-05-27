package server

import (
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/encoding/protojson"

	"gitlab.suredatalab.kr/beymons/devices"
)

var jsonMarshaler = protojson.MarshalOptions{
	UseProtoNames:     true,
	UseEnumNumbers:    false,
	EmitUnpopulated:   false,
	EmitDefaultValues: false,
}

// 에러 코드 정의
const (
	SUCCESS                          uint32 = 0
	NO_SUCH_FILE_OR_DIRECTORY        uint32 = 2
	NO_SUCH_DEVICE_OR_ADDRESS        uint32 = 6
	RESOURCE_TEMPORARILY_UNAVAILABLE uint32 = 11
	NO_SUCH_DEVICE                   uint32 = 19
	INVALID_ARGUMENT                 uint32 = 22
	FUNCTION_NOT_IMPLEMENTED         uint32 = 38
	NO_DATA_AVAILABLE                uint32 = 61
	TIMER_EXPIRED                    uint32 = 62
)

type DeviceProvider struct {
	auth.VerifyProvider
}

func (p DeviceProvider) Verify(name string, claims *auth.Claims, payload any) error {
	if claims.IsAdmin() {
		return nil
	}

	// 기본 권한 확인
	result := false
	for _, role := range auth.GetRole(name) {
		if claims.HasRole(role) {
			result = true
		}
	}
	if !result {
		return auth.ErrAccessDenied.Err()
	}

	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	// 장치 관리자만 전체 리스트를 조회할 수 있음
	query := conn.Model((*devices.Device)(nil))

	if pgorm.ExistTable(conn, "site_devices") {
		query.Join("JOIN site_devices USING (device_id)")
		query.Join("JOIN site_users USING (site_id)")
		query.Where("user_id = ?", claims.UserID)
	}

	switch name {
	// 조회 권한 처리
	case "/devices.Devices/GetDevice",
		"/devices.Devices/Histories":
		req := payload.(*devices.DeviceRequest)
		query.Where("device_id = ?", req.DeviceId)

	case "/devices.Devices/GetSensorLimit":
		req := payload.(*devices.GetLimitRequest)
		query.Where("device_id = ?", req.DeviceId)

	default:
		// API 내부에서 확인
		return nil
	}

	if exists, err := query.Exists(); err != nil {
		log.Error("Failed to check rbac", "error", err)
	} else if exists {
		return nil
	}
	return auth.ErrAccessDenied.Err()
}
