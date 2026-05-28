package server

import (
	"context"
	"fmt"
	"strings"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/devices"
)

// Histories - 장치 관리 이력 조회
func (s DevicesServer) Histories(ctx context.Context, req *devices.DeviceRequest) (*devices.HistoryResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	query := historyQuery(ctx, conn, req.DeviceId)
	res := &devices.HistoryResponse{}
	if err := query.ForEach(func(tuple *devices.DeviceHistory) error {
		res.Histories = append(res.Histories, proto.Clone(tuple).(*devices.DeviceHistory))
		tuple = nil
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return res, nil
}

// 이력 조회
func historyQuery(ctx context.Context, conn *pg.Conn, deviceID string) *pg.Query {
	query := conn.ModelContext(ctx, (*devices.DeviceHistory)(nil))
	query.Column("created_at", "device_id", "action", "created_user_id")
	query.Where("device_id = ?", deviceID)
	query.Order("created_at ASC")

	// 사용자 정보
	exists := pgorm.JoinUserInfo(conn, query, "created_user_id")
	if exists {
		query.ColumnExpr("TO_JSON(user_info) created_by")
	}

	// 변경 이력
	updateQuery := conn.Model((*devices.DeviceUpdateHistory)(nil))
	updateQuery.Column("created_at", "device_id")
	updateQuery.ColumnExpr("JSON_OBJECT_AGG(attribute, JSON_BUILD_OBJECT('origin', origin, 'change', change)) AS details")
	updateQuery.Where("device_id = ?", deviceID)
	updateQuery.Group("created_at", "device_id")
	updateQuery.Where("attribute NOT IN ('sensors', 'parent', 'children', 'sites', 'facilities')")
	query.With("updated", updateQuery).Join("LEFT JOIN updated USING (created_at, device_id)")

	// 연결 이력
	connQuery := conn.Model((*devices.DeviceUpdateHistory)(nil))
	connQuery.Column("created_at", "device_id", "attribute")
	connQuery.ColumnExpr("JSON_BUILD_OBJECT(attribute, JSON_AGG(COALESCE(change, origin))) AS details")
	connQuery.Where("device_id = ?", deviceID)
	connQuery.Group("created_at", "device_id", "attribute")
	connQuery.Where("attribute IN ('sensors', 'parent', 'children', 'sites', 'facilities')")
	query.With("connected", connQuery).Join("LEFT JOIN connected USING (created_at, device_id)")

	// 상태 이력
	statusQuery := conn.Model((*devices.DeviceStatusHistory)(nil))
	statusQuery.Column("created_at", "device_id")
	statusQuery.ColumnExpr("LAST(status, created_at) FILTER (WHERE channel IS NULL) AS status")
	statusQuery.ColumnExpr("JSON_OBJECT_AGG(channel::varchar, JSON_BUILD_OBJECT('status', status, 'description', description)) FILTER (WHERE channel IS NOT NULL) AS details")
	statusQuery.Where("device_id = ?", deviceID)
	statusQuery.Group("created_at", "device_id")
	query.With("status", statusQuery).Join("LEFT JOIN status USING (created_at, device_id)")

	// details
	details := []string{
		"CASE action",
		fmt.Sprintf("WHEN '%s' THEN updated.details", devices.DeviceHistory_Kind_name[int32(devices.DeviceHistory_UPDATE)]),
		fmt.Sprintf("WHEN '%s' THEN connected.details", devices.DeviceHistory_Kind_name[int32(devices.DeviceHistory_ATTACH)]),
		fmt.Sprintf("WHEN '%s' THEN connected.details", devices.DeviceHistory_Kind_name[int32(devices.DeviceHistory_DETACH)]),
		fmt.Sprintf("WHEN '%s' THEN connected.details", devices.DeviceHistory_Kind_name[int32(devices.DeviceHistory_INSTALL)]),
		fmt.Sprintf("WHEN '%s' THEN connected.details", devices.DeviceHistory_Kind_name[int32(devices.DeviceHistory_UNINSTALL)]),
		fmt.Sprintf("WHEN '%s' THEN status.details", devices.DeviceHistory_Kind_name[int32(devices.DeviceHistory_STATUS)]),
		"END details",
	}

	return query.ColumnExpr(strings.Join(details, " "))
}

// 이력 기록
func writeHistory(ctx context.Context, tx *pg.Tx, deviceID, userID string, action devices.DeviceHistory_Kind, content interface{}) error {
	log.Infof("Write history of %q: %s", deviceID, action)

	// 이력 기록
	history := &devices.DeviceHistory{
		DeviceId:      deviceID,
		Action:        action,
		CreatedUserId: userID,
	}
	if _, err := tx.ModelContext(ctx, history).Returning("created_at").Insert(); err != nil {
		return pgorm.GetError(ctx, err)
	}

	refresh := true
	switch action {
	case devices.DeviceHistory_CREATE:
		// 정상 상태로 등록
		if _, err := tx.ModelContext(ctx, &devices.DeviceStatusHistory{
			CreatedAt: history.CreatedAt,
			DeviceId:  deviceID,
			Status:    devices.DeviceStatus_NORMAL,
		}).Insert(); err != nil {
			return pgorm.GetError(ctx, err)
		}

	case
		devices.DeviceHistory_ATTACH,
		devices.DeviceHistory_DETACH,
		devices.DeviceHistory_INSTALL,
		devices.DeviceHistory_UNINSTALL,
		devices.DeviceHistory_UPDATE:
		changed := content.([]*devices.DeviceUpdateHistory)
		for _, device := range changed {
			device.CreatedAt = history.CreatedAt
			device.DeviceId = deviceID
		}

		log.Debugf("%+v", changed)

		// 변경 이력 추가
		if _, err := tx.ModelContext(ctx, &changed).Insert(); err != nil {
			return pgorm.GetError(ctx, err)
		}

	case devices.DeviceHistory_DELETE:
		// 폐기 상태로 변경
		if _, err := tx.ModelContext(ctx, &devices.DeviceStatusHistory{
			CreatedAt: history.CreatedAt,
			DeviceId:  deviceID,
			Status:    devices.DeviceStatus_DISCARD,
		}).Insert(); err != nil {
			return pgorm.GetError(ctx, err)
		}

	case devices.DeviceHistory_STATUS:
		refresh = false
		// 상태 기록
		statusHistory := content.(*devices.DeviceStatusHistory)
		statusHistory.DeviceId = deviceID
		statusHistory.CreatedAt = history.CreatedAt
		if _, err := tx.ModelContext(ctx, statusHistory).Insert(); err != nil {
			return pgorm.GetError(ctx, err)
		}
	}

	if refresh {
		if _, err := tx.ExecContext(ctx, "REFRESH MATERIALIZED VIEW CONCURRENTLY view_device_summary"); err != nil {
			return pgorm.GetError(ctx, err)
		}
	}

	return nil
}
