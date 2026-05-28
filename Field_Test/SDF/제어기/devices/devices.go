package devices

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"gitlab.suredatalab.kr/sdlmicro/types"
	"gitlab.suredatalab.kr/services/metadata"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/structpb"
)

// MetricDescriptor 함수는 센서에 대한 디스크립터를 가져온다.
func (s *Sensor) MetricDescriptor(conn *pg.Conn) (map[string]*types.MetricDescriptor, error) {
	entities := make(map[string]*types.MetricDescriptor)
	query := conn.Model((*SensorTypeAttribute)(nil)).Where("type_id = ?", s.SensorType)
	caseStat := []string{
		fmt.Sprintf("WHEN '%s' THEN '%s'", metadata.MetadataSchemaAttribute_boolean, types.MetricDescriptor_bool),
		fmt.Sprintf("WHEN '%s' THEN '%s'", metadata.MetadataSchemaAttribute_real, types.MetricDescriptor_double),
		fmt.Sprintf("WHEN '%s' THEN '%s'", metadata.MetadataSchemaAttribute_double_precision, types.MetricDescriptor_double),
		fmt.Sprintf("WHEN '%s' THEN '%s'", metadata.MetadataSchemaAttribute_bigint, types.MetricDescriptor_int64),
		fmt.Sprintf("WHEN '%s' THEN '%s'", metadata.MetadataSchemaAttribute_integer, types.MetricDescriptor_int64),
		fmt.Sprintf("WHEN '%s' THEN '%s'", metadata.MetadataSchemaAttribute_smallint, types.MetricDescriptor_int64),
		fmt.Sprintf("ELSE '%s'", types.MetricDescriptor_string),
	}

	query.Column("attribute", "unit", "description")
	query.ColumnExpr(fmt.Sprintf("CASE REPLACE(type_name, ' ', '_') %s END type_name", strings.Join(caseStat, " ")))
	if err := query.ForEach(func(tuple *SensorTypeAttribute) error {
		entities[tuple.Attribute] = &types.MetricDescriptor{
			Id:          tuple.Attribute,
			DisplayName: tuple.Attribute,
			Unit:        tuple.Unit,
			ValueType:   types.MetricDescriptor_ValueType(types.MetricDescriptor_ValueType_value[tuple.TypeName]),
			Description: tuple.Description,
		}
		return nil
	}); err != nil {
		return nil, err
	}

	return entities, nil
}

// LatestData 함수는 센서에서 가장 최근에 수집된 데이터를 가져온다.
func (s *Sensor) LatestData(conn *pg.Conn, attributes map[string]*types.MetricDescriptor) error {
	var multiProbe bool
	if err := conn.Model((*SensorType)(nil)).
		Where("type_id = ?", s.SensorType).
		Column("multi_probe").
		Select(&multiProbe); err != nil {
		return err
	}

	query := conn.Model().Table(s.SensorType).Where("sensor_id = ?", s.SensorId)
	query.Column("ts").Order("ts DESC")
	query.Where("ts >= now() - INTERVAL '1 week'")
	query.Where("invalid = FALSE")
	for name := range attributes {
		query.Column(name)
	}

	if multiProbe {
		query.Column("probe")
		query.ColumnExpr("ROW_NUMBER() OVER (PARTITION BY probe ORDER BY ts DESC) as r")
		query = query.WrapWith("entities").Table("entities")
		query.Where("r = 1")
		query.Order("ts")
	}

	var tuples []map[string]interface{}
	if err := query.Select(&tuples); err != nil {
		return err
	}

	lastValue := make(map[string]*structpb.Value)

	result := &structpb.Struct{Fields: make(map[string]*structpb.Value)}
	for _, tuple := range tuples {
		res := &structpb.Struct{Fields: make(map[string]*structpb.Value)}
		var probe string
		for k, v := range tuple {
			switch k {
			case "ts":
				res.Fields["ts"] = structpb.NewNumberValue(float64(v.(time.Time).UnixMilli()))
			case "probe":
				probe = fmt.Sprint(v)

			case "r": // 처리할 필요 없음

			default:
				switch v.(type) {
				case bool:
					res.Fields[k] = structpb.NewBoolValue(v.(bool))
				case float32:
					res.Fields[k] = structpb.NewNumberValue(float64(v.(float32)))
				case float64:
					res.Fields[k] = structpb.NewNumberValue(v.(float64))
				case int16:
					res.Fields[k] = structpb.NewNumberValue(float64(v.(int16)))
				case int32:
					res.Fields[k] = structpb.NewNumberValue(float64(v.(int32)))
				case int64:
					res.Fields[k] = structpb.NewNumberValue(float64(v.(int64)))
				default:
					res.Fields[k] = structpb.NewStringValue(fmt.Sprint(v))
				}

				lastValue[k] = res.Fields[k]
			}
		}

		if !multiProbe {
			s.Latest = res
			return nil
		}

		result.Fields[probe] = structpb.NewStructValue(res)
	}

	// 일부 타입에 추가 정보 제공
	switch s.SensorType {
	case "agsmotor":
		result.Fields["mode"] = lastValue["mode"]
	}

	s.Latest = result
	return nil
}

// Set 함수는 센서에 대한 임계치를 적용한다.
func (sl *SensorLimit) Set(ctx context.Context, conn *pg.Conn) error {
	// 센서 및 타입 확인
	var sensroType string
	query := conn.ModelContext(ctx, (*Sensor)(nil)).Where("device_id = ?", sl.DeviceId)
	query.Join("LEFT JOIN sensor_type_attributes").JoinOn("type_id = sensor_type AND attribute = ?", sl.Attribute)
	query.Where("channel_id = ?", sl.Channel)
	if err := query.Column("type_id").Select(&sensroType); err != nil {
		return pgorm.GetError(ctx, err)
	}

	if len(sensroType) == 0 {
		return status.Errorf(codes.InvalidArgument, "No matching attribute %q", sl.Attribute)
	}

	// 리밋 설정
	query = conn.ModelContext(ctx, sl)
	query.OnConflict("(device_id, channel, attribute) DO UPDATE")
	query.Set("normal_min = EXCLUDED.normal_min")
	query.Set("normal_max = EXCLUDED.normal_max")
	query.Set("caution_min = EXCLUDED.caution_min")
	query.Set("caution_max = EXCLUDED.caution_max")
	if _, err := query.Insert(); err != nil {
		return pgorm.GetError(ctx, err)
	}

	return nil
}
