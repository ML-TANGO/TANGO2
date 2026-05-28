package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/devices"
)

// GetCommand - 명령 처리 상태 확인 API
func (s DevicesServer) GetCommand(ctx context.Context, req *devices.GetCommandRequest) (*devices.DeviceCommandHistory, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	cmd := &devices.Command{
		Downstream: true,
	}

	// 사이트 연결 정보
	query := conn.ModelContext(ctx, (*devices.Device)(nil))
	query.Where("device_role = ?", devices.DeviceRole_GATEWAY)
	query.Join("LEFT JOIN device_relations").JoinOn("parent_id = device_id AND child_id = ?", req.DeviceId) // DEPRECATED: 제거 예정
	query.Join("JOIN site_devices USING (device_id)")
	query.Join("JOIN sites USING (site_id)")
	query.Column("sites.application", "site_id")
	if pgorm.ExistTable(conn, "last_received_histories") {
		// 데이터 수신 기록을 활용하여 게이트웨이 확인
		query.Join("LEFT JOIN last_received_histories lrh").JoinOn("gateway_id = device.device_id AND lrh.device_id = ?", req.DeviceId)
		query.ColumnExpr("COALESCE(gateway_id, device.device_id)")
	} else {
		query.Column("device_id")
	}

	if err := query.Limit(1).Select(&cmd.Kind, &cmd.SiteId, &cmd.GatewayId); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 처리 상태 확인
	resp := &devices.DeviceCommandHistory{}
	query = conn.ModelContext(ctx, resp)
	query.Where("device_id = ?", cmd.GatewayId)
	query.Where("sequence = ?", req.Sequence)
	query.Where("direction = ?", devices.DeviceCommandHistory_downstream)
	if err := query.Select(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return resp, nil
}
