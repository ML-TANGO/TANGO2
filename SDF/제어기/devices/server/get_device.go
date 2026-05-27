package server

import (
	"context"
	"fmt"
	"strings"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"gitlab.suredatalab.kr/sdlmicro/types"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/devices"
)

// GetDevice - 장치 조회
func (s DevicesServer) GetDevice(ctx context.Context, req *devices.DeviceRequest) (*devices.DeviceResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	res := &devices.DeviceResponse{
		Device: &devices.Device{},
		Link: map[string]string{
			"histories": fmt.Sprintf("/api/devices/%s/histories", req.DeviceId),
		},
	}

	// 장치 정보 조회
	res.Device, err = getDevice(ctx, conn, req.DeviceId)
	if err != nil {
		return nil, err
	}

	// 하위 장치 정보 추가
	query := deviceQuery(ctx, conn)
	query.Join("JOIN device_relations").JoinOn("child_id = device_id")
	query.Where("parent_id = ?", req.DeviceId)
	query.With("sensor", sensorQuery(ctx, conn)).Join("LEFT JOIN sensor USING (device_id)")
	query.Column("sensors")
	if err := query.ForEach(func(tuple *devices.Device) error {
		res.Related = append(res.Related, proto.Clone(tuple).(*devices.Device))
		tuple = nil
		return nil
	}); err != nil {
		log.Warn("Failed to find child devices", "error", err)
	}

	// TODO: 장치 설정 확인

	// 관련 링크 (HATEOAS)
	if res.Device.Site != nil && len(res.Device.Site.SiteId) > 0 {
		res.Link["site"] = fmt.Sprintf("/api/sites/%s", res.Device.Site.SiteId)
	}
	return res, nil
}

// 장치 조회
func getDevice(ctx context.Context, conn *pg.Conn, deviceID string) (*devices.Device, error) {
	var resp devices.Device
	// 장치 정보 조회
	query := deviceQuery(ctx, conn)
	query.With("sensor", sensorQuery(ctx, conn).Where("sensor.device_id = ?", deviceID))
	query.Join("LEFT JOIN sensor USING (device_id)")
	query.Column("sensors")
	if err := query.Where("device_id = ?", deviceID).Select(&resp); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	var err error
	// 최근 데이터 조회
	sensorTypes := make(map[string]map[string]*types.MetricDescriptor)
	for _, sensor := range resp.Sensors {
		if _, ok := sensorTypes[sensor.SensorType]; !ok {
			sensorTypes[sensor.SensorType], err = sensor.MetricDescriptor(conn)
			if err != nil {
				log.Warnf("Cannot get MetricDescriptor of %q. %s", sensor.SensorType, err.Error())
				continue
			}
		}

		sensor.LatestData(conn, sensorTypes[sensor.SensorType])
	}

	return &resp, nil
}

// 센서 조회 쿼리
func sensorQuery(ctx context.Context, conn *pg.Conn) *pg.Query {
	// 센서 목록
	query := conn.Model((*devices.Sensor)(nil))
	query.Column("sensor.device_id")
	query.Group("sensor.device_id")

	columns := []string{
		"'device_id', sensor.device_id",
		"'sensor_id', sensor_id",
		"'channel_id', channel_id",
		"'sensor_type', sensor_type",
		"'display_name', display_name",
		"'probes', probes",
		"'status', sensor.status",
	}

	// 설비 정보
	if pgorm.ExistTable(conn, "facility_devices") {
		query.Join("LEFT JOIN facility_devices fd")
		query.JoinOn("fd.device_id = sensor.device_id")
		query.JoinOn("modbus = channel_id")
		query.Join("LEFT JOIN facilities USING (facility_id)")

		columns = append(columns, "'facility', JSONB_BUILD_OBJECT('id', facility_id, 'name', facility_name)")
		columns = append(columns, "'description', fd.description")
	} else {
		columns = append(columns, "'description', sensor.description")
	}

	return query.ColumnExpr(fmt.Sprintf("JSONB_AGG(JSONB_BUILD_OBJECT(%s)) sensors", strings.Join(columns, ", ")))
}

// 장치 조회 쿼리
func deviceQuery(ctx context.Context, conn *pg.Conn) *pg.Query {
	query := conn.ModelContext(ctx, (*devices.Device)(nil))
	query.Column("device_id", "device_role", "device.status")

	// 이력 조인 쿼리
	query.Join("JOIN view_device_summary history USING (device_id)")
	query.Column("history.created_at", "history.updated_at")
	if pgorm.JoinUserInfo(conn, query, "history.created_user_id") {
		query.ColumnExpr("COALESCE(TO_JSONB(user_info), JSONB_BUILD_OBJECT('user_id', history.created_user_id, 'name', history.created_name)) created_by")
		query.Join("LEFT JOIN user_info updated").JoinOn("updated.user_id = updated_user_id")
		query.ColumnExpr("COALESCE(TO_JSONB(updated), JSONB_BUILD_OBJECT('user_id', history.updated_user_id, 'name', history.updated_name)) updated_by")
	} else {
		query.ColumnExpr("JSONB_BUILD_OBJECT('user_id', history.created_user_id, 'name', history.created_name) created_by")
		query.ColumnExpr("JSONB_BUILD_OBJECT('user_id', history.updated_user_id, 'name', history.updated_name) updated_by")
	}

	// 연결 정보
	existsSite := pgorm.ExistTable(conn, "site_devices")
	if existsSite {
		// 사이트로 출고된 장치는 사이트 정보 및 위치 표시
		siteQuery := conn.Model().Table("site_devices")
		siteQuery.Join("JOIN sites USING (site_id)")
		siteQuery.Column("device_id", "site_id", "site_name")
		siteQuery.ColumnExpr("NULLIF(site_devices.display_name, '') display_name")
		siteQuery.ColumnExpr("NULLIF(site_devices.description, '') description")
		siteQuery.ColumnExpr("COALESCE(site_devices.latitude, sites.latitude) AS latitude")
		siteQuery.ColumnExpr("COALESCE(site_devices.longitude, sites.longitude) AS longitude")
		siteQuery.ColumnExpr("COALESCE(site_devices.altitude, sites.altitude) AS altitude")

		query.With("site_info", siteQuery).Join("LEFT JOIN site_info USING (device_id)")
		query.ColumnExpr("site_id AS site__site_id")
		query.ColumnExpr("site_name AS site__site_name")
		query.ColumnExpr("COALESCE(site_info.display_name, device.display_name) AS display_name")
		query.ColumnExpr("COALESCE(site_info.description, device.description) AS description")

		query.ColumnExpr("site_info.latitude AS location__latitude")
		query.ColumnExpr("site_info.longitude AS location__longitude")
		query.ColumnExpr("site_info.altitude AS location__altitude")
	} else {
		query.Column("device.display_name", "device.description")
		query.ColumnExpr("NULL AS site__site_id")
		query.ColumnExpr("NULL AS site__site_name")
		query.ColumnExpr("NULL AS location__latitude")
		query.ColumnExpr("NULL AS location__longitude")
		query.ColumnExpr("NULL AS location__altitude")
	}

	// 권한 확인
	if claims, err := auth.GetClaim(ctx); err == nil {
		if claims.IsAdmin() {
			query.ColumnExpr("TRUE AS writable")
		} else if existsSite {
			authQuery := conn.Model().Table("site_users")
			authQuery.Join("JOIN site_devices USING (site_id)")
			authQuery.Column("device_id", "user_id", "role")
			authQuery.Where("user_id = ?", claims.UserID)
			query.With("users", authQuery).Join("JOIN users USING (device_id)")
			query.ColumnExpr("CASE users.role WHEN 'user' THEN FALSE ELSE TRUE END writable")
		} else if claims.HasRole("manage-devices") {
			// 사이트 서비스 없이 단독으로 동작하는 경우
			query.ColumnExpr("TRUE AS writable")
		} else {
			query.ColumnExpr("FALSE AS writable")
		}
	} else {
		query.Where("device_id IS NULL")
	}

	return query
}
