package server

import (
	"context"
	"fmt"
	"strings"

	"github.com/go-pg/pg/v10"
	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"gitlab.suredatalab.kr/services/metadata"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/devices"
)

// SearchType - 센서 타입 조회
func (s DevicesServer) SearchType(ctx context.Context, req *devices.SearchTypeRequest) (*devices.SearchTypeResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	query := sensorTypeQuery(ctx, conn)

	// 조회 필드 처리
	if req.Field == nil {
		for k := range devices.SearchTypeRequest_Attribute_name {
			req.Field = append(req.Field, (devices.SearchTypeRequest_Attribute)(k))
		}
	}

	query = query.WrapWith("list").Table("list")
	query.Column("type_id", "multi_probe", "writable")

	// 조회 필드 처리
	for _, fieldID := range req.Field {
		switch fieldID {
		case devices.SearchTypeRequest_sensor_type_id: // Default

		default:
			query.Column(devices.SearchTypeRequest_Attribute_name[int32(fieldID)])
		}
	}

	// 전체 검색
	if len(req.Search) > 0 {
		query.WhereGroup(func(q *pg.Query) (*pg.Query, error) {
			q.WhereOr(fmt.Sprintf("type_id ILIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("type_name ILIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("description ILIKE '%%%s%%'", req.Search))
			return q, nil
		})
	}

	if len(req.TypeId) > 0 {
		query.Where("type_id = ?", req.TypeId)
	}

	res := &devices.SearchTypeResponse{Link: map[string]string{}}
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
	order := func(order []devices.SearchTypeRequest_Attribute, desc bool) {
		for _, field := range order {
			var fieldName string
			switch field {
			case devices.SearchTypeRequest_sensor_type_id:
				fieldName = "type_id"

			case devices.SearchTypeRequest_created_by:
				fieldName = "created_by->>'name'"

			case devices.SearchTypeRequest_attributes:
				fieldName = "JSON_ARRAY_LENGTH(attributes)"

			default:
				fieldName = devices.SearchTypeRequest_Attribute_name[int32(field)]
			}

			if desc {
				query.OrderExpr(fmt.Sprintf("%s DESC NULLS LAST", fieldName))
			} else {
				query.OrderExpr(fmt.Sprintf("%s NULLS LAST", fieldName))
			}
		}
	}
	order(req.Asc, false)
	order(req.Desc, true)

	// 조회
	if req.Limit > 0 {
		query.Limit(int(req.Limit)).Offset(int(req.Offset)) // 조회 결과 제한
	}
	if err := query.ForEach(func(tuple *devices.SensorType) error {
		res.Entities = append(res.Entities, proto.Clone(tuple).(*devices.SensorType))
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

// 센서 타입 조회 쿼리
func sensorTypeQuery(ctx context.Context, conn *pg.Conn) *pg.Query {
	query := conn.ModelContext(ctx, (*devices.SensorType)(nil)).Group("type_id")
	query.Column("type_id", "multi_probe", "created_at", "created_user_id")
	query.Column("sensor_type.type_name", "sensor_type.description")

	attrQuery := conn.Model((*devices.SensorTypeAttribute)(nil))
	attrQuery.Column("type_id", "attribute", "unit", "type_name", "description")

	var caseStat []string
	for k, v := range metadata.MetadataSchemaAttribute_Type_value {
		caseStat = append(caseStat, fmt.Sprintf("WHEN '%s' THEN %d", k, v))
	}
	attrQuery.ColumnExpr(fmt.Sprintf("CASE REPLACE(type_name, ' ', '_') %s ELSE %d END type", strings.Join(caseStat, " "), metadata.MetadataSchemaAttribute_text))
	attrQuery.ColumnExpr("CASE WHEN type_name LIKE 'varchar%' THEN LEFT(REGEXP_REPLACE(type_name, '[^\\d]+', ''), -1)::int ELSE 0 END length")

	query.With("attr", attrQuery).Join("JOIN attr USING (type_id)")
	query.ColumnExpr("JSON_AGG(attr) attributes")

	if pgorm.JoinUserInfo(conn, query, "created_user_id") {
		query.ColumnExpr("TO_JSON(LAST(user_info, created_at)) AS created_by")
	} else {
		query.ColumnExpr("'{}'::json AS created_by")
	}

	if claims, err := auth.GetClaim(ctx); err != nil && claims.HasRole("manage-sensor-types") {
		query.ColumnExpr("TRUE AS writable")
	} else {
		query.ColumnExpr("FALSE AS writable")
	}

	return query
}
