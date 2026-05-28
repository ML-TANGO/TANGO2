package server

import (
	"context"
	"time"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"gitlab.suredatalab.kr/sdlmicro/types"
	"google.golang.org/protobuf/types/known/anypb"
	"google.golang.org/protobuf/types/known/timestamppb"
	"google.golang.org/protobuf/types/known/wrapperspb"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// Stat - 설비 현재 상태 조회 API
func (s FacilitiesServer) Stat(ctx context.Context, req *facilities.FacilityRequest) (*facilities.StatResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	query := conn.ModelContext(ctx, (*facilities.FacilityDevice)(nil))
	query.Column("sensor_id", "sensor_type", "modbus", "channel", "unit", "st.description")
	query.Join("JOIN sensors s").JoinOn("s.device_id = facility_device.device_id AND channel_id = modbus")
	query.Where("facility_id = ?", req.FacilityId)
	query.Join("JOIN sensor_type_attributes st").JoinOn("type_id = sensor_type")

	resp := &facilities.StatResponse{
		Stat: make(map[string]*types.Metric),
	}

	for _, attribute := range []string{"temp", "humi"} {
		// 대상 센서 조회
		var entities []*Stat
		tempQuery := query.Clone().Where("attribute = ?", attribute)
		if err := tempQuery.Select(&entities); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}

		var total float64
		var count int
		for _, info := range entities {
			var value float64
			var ts time.Time
			q := conn.ModelContext(ctx).Table(info.SensorType)
			q.Where("sensor_id = ?", info.SensorID)
			q.Where("invalid IS FALSE")
			q.Where("ts >= NOW() - INTERVAL '1 HOUR'")
			if info.Channel > 0 {
				q.Where("probe = ?", info.Channel)
			}
			q.OrderExpr("ts DESC").Limit(1)
			if err := q.Column("ts", attribute).Select(&ts, &value); err != nil {
				if err == pg.ErrNoRows {
					continue
				}
				return nil, pgorm.GetError(ctx, err)
			}

			if _, ok := resp.Stat[attribute]; !ok {
				resp.Stat[attribute] = &types.Metric{
					Descriptor_: &types.MetricDescriptor{
						Id:          attribute,
						DisplayName: info.Description,
						MetricKind:  types.MetricDescriptor_gauge,
						ValueType:   types.MetricDescriptor_double,
						Unit:        info.Unit,
					},
					Ts: timestamppb.New(ts),
				}
			}

			count++
			total += value
			if ts.After(resp.Stat[attribute].Ts.AsTime()) {
				resp.Stat[attribute].Ts = timestamppb.New(ts)
			}
		}

		if _, ok := resp.Stat[attribute]; ok {
			tmp := &wrapperspb.DoubleValue{Value: total / float64(count)}
			value, err := anypb.New(tmp)
			if err != nil {
				log.InternalError(ctx, err)
			}
			resp.Stat[attribute].Value = value
		}
	}

	return resp, nil
}

type Stat struct {
	SensorID    string
	SensorType  string
	Modbus      uint32
	Channel     uint32
	Unit        string
	Description string
}
