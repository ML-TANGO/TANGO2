package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/devices"
)

// Devices - 설비에 연결된 장치 조회
func (s FacilitiesServer) Devices(ctx context.Context, req *devices.SearchRequest) (*devices.SearchResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	// 기존 정보 조회
	log.Debug("load origin model...")
	origin, err := getFacility(ctx, conn, req.FacilityId)
	if err != nil {
		return nil, err
	}

	return devices.Client().Search(ctx, &devices.SearchRequest{
		SiteId:     origin.SiteId,
		FacilityId: req.FacilityId,
		SensorType: req.SensorType,
	})
}
