package server

import (
	"context"
	"fmt"

	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	collects "gitlab.suredatalab.kr/beymons/collects"
)

// Statistics - 통계
func (s CollectsServer) Statistics(ctx context.Context, req *collects.StatisticsRequest) (*collects.StatisticsResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	interval := fmt.Sprintf("1 %s", collects.StatisticsRequest_Interval_name[(int32(req.Interval))])
	if len(req.Timezone) == 0 {
		req.Timezone = "Z"
	}

	query := conn.ModelContext(ctx, (*collects.ReceiveHistory)(nil))
	query.ColumnExpr("EXTRACT(epoch FROM processed_at - received_at) AS work_time")
	query.Column("size", "error", "nodes", "sensors", "recorded")
	query.ColumnExpr("time_bucket(?, received_at, timezone => ?) AS created_at", interval, req.Timezone)
	if len(req.SiteId) > 0 {
		query.Where("site_id = ?", req.SiteId)
	}

	query = query.WrapWith("stat").Table("stat")
	query.Group("created_at").Column("created_at")
	query.OrderExpr("created_at DESC")
	query.ColumnExpr("COUNT(1) received")
	query.ColumnExpr("SUM(size) size")
	query.ColumnExpr("COUNT(error) error")
	query.ColumnExpr("SUM(work_time) FILTER (WHERE error IS NULL)::bigint AS work_time")
	query.ColumnExpr("SUM(nodes) nodes")
	query.ColumnExpr("SUM(sensors) sensors")
	query.ColumnExpr("SUM(recorded) recorded")

	res := &collects.StatisticsResponse{}
	if err := query.ForEach(func(tuple *collects.StatisticsResponse_Statistics) error {
		res.Entities = append(res.Entities, proto.Clone(tuple).(*collects.StatisticsResponse_Statistics))
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return res, nil
}
