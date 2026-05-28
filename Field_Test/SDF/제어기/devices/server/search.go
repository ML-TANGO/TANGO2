package server

import (
	"context"
	"fmt"
	"strings"

	"github.com/go-pg/pg/v10"
	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/devices"
)

// Search - 장치 검색
func (s DevicesServer) Search(ctx context.Context, req *devices.SearchRequest) (*devices.SearchResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	// 조회 필드 처리
	if req.Field == nil {
		for k := range devices.Attribute_name {
			req.Field = append(req.Field, (devices.Attribute)(k))
		}
	}

	query := deviceQuery(ctx, conn)
	sensors := sensorQuery(ctx, conn)
	query.With("sensor", sensors).Join("LEFT JOIN sensor USING (device_id)").Column("sensors")
	query = query.WrapWith("list").Table("list")
	query.Column("device_id", "device_role", "status", "writable", "sensors")

	// 조회 필드 처리
	for _, fieldID := range req.Field {
		switch fieldID {
		case devices.Attribute_site:
			query.Column("site__site_id")
			query.Column("site__site_name")

		case devices.Attribute_location:
			query.Column("location__latitude")
			query.Column("location__longitude")
			query.Column("location__altitude")

		default:
			query.Column(devices.Attribute_name[int32(fieldID)])
		}
	}

	// 전체 검색
	if len(req.Search) > 0 {
		query.WhereGroup(func(q *pg.Query) (*pg.Query, error) {
			q.WhereOr(fmt.Sprintf("device_id ILIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("display_name ILIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("description ILIKE '%%%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("site__site_id ILIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("site__site_name ILIKE '%%%s%%'", req.Search))
			return q, nil
		})
	}

	// 장치 ID로 필터링
	if len(req.DeviceId) > 0 {
		query.Where("device_id = ?", req.DeviceId)
	}

	// 사이트 ID로 필터링
	if len(req.SiteId) > 0 {
		query.Where("site__site_id = ?", req.SiteId)
	}

	// 설비 ID로 필터링
	if len(req.FacilityId) > 0 {
		if pgorm.ExistTable(conn, "facility_devices") {
			sensors.Where("facility_id = ?", req.FacilityId)
			query.Where("sensors IS NOT NULL")
		} else {
			query.Where("device_id IS NULL")
		}
	}

	// 보유한 센서의 타입으로 필터링
	if len(req.SensorType) > 0 {
		typeQuery := conn.Model((*devices.Sensor)(nil))
		typeQuery.WhereIn("sensor_type IN (?)", req.SensorType)
		typeQuery.Group("device_id").Column("device_id")
		query.With("has_type", typeQuery).Join("JOIN has_type USING(device_id)")
	}

	// 장치 구분으로 필터링
	if len(req.Role) > 0 {
		query.WhereIn("device_role IN (?)", req.Role)
	}

	// 장치 상태로 필터링
	if len(req.Status) > 0 {
		query.WhereIn("status IN (?)", req.Status)
	}

	res := &devices.SearchResponse{Link: make(map[string]string)}
	if req.Limit > 0 {
		// 총 수
		count, err := query.Count()
		if err != nil {
			return nil, pgorm.GetError(ctx, err)
		} else if count == 0 {
			return res, nil
		} else {
			res.Count = uint64(count)
		}
	}

	// 정렬
	for _, order := range req.Order {
		var column string
		switch order {
		case devices.SearchRequest_site_id_asc:
			column = "site__site_id"
		case devices.SearchRequest_site_id_desc:
			column = "site__site_id DESC"
		case devices.SearchRequest_site_name_asc:
			column = "site__site_name"
		case devices.SearchRequest_site_name_desc:
			column = "site__site_name DESC"

		default:
			var ok bool
			column, ok = strings.CutSuffix(devices.SearchRequest_Order_name[int32(order)], "_desc")
			if ok {
				column += " DESC"
			} else {
				column, _ = strings.CutSuffix(devices.SearchRequest_Order_name[int32(order)], "_asc")
			}
		}
		query.OrderExpr(column + " NULLS LAST")
	}

	// 조회
	if req.Limit > 0 {
		query.Limit(int(req.Limit)).Offset(int(req.Offset)) // 조회 결과 제한
	}
	if err := query.ForEach(func(tuple *devices.Device) error {
		res.Entities = append(res.Entities, proto.Clone(tuple).(*devices.Device))
		tuple = nil
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	if res.Count == 0 {
		res.Count = uint64(len(res.Entities))
	}

	sdlmicro.SetPagination(ctx, req.Limit, req.Offset, res.Count, res.Link)
	return res, nil
}
