package server

import (
	"context"
	"fmt"
	"strings"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"gitlab.suredatalab.kr/services/metadata"

	"gitlab.suredatalab.kr/beymons/devices"
)

// CreateType - 샌서 타입 생성
func (s DevicesServer) CreateType(ctx context.Context, req *devices.SensorType) (*devices.SensorType, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 사용자 정보 조회
	claims, err := auth.GetClaim(ctx)
	if err != nil {
		return nil, err
	}

	log.Infof("Create sensor type %q", req.TypeId)
	req.CreatedUserId = claims.UserID
	req.CreatedAt = nil
	if _, err := tx.ModelContext(ctx, req).Insert(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 센서 타입의 컬럼
	columns := []string{
		"ts timestamptz NOT NULL DEFAULT NOW()",
		"site_id varchar(50) NOT NULL",
		"sensor_id uuid NOT NULL",
		"invalid boolean NOT NULL DEFAULT FALSE",
	}
	indexColumn := []string{"ts DESC", "site_id ASC", "sensor_id ASC"}
	if req.MultiProbe {
		columns = append(columns, "probe smallint NOT NULL")
		indexColumn = append(indexColumn, "probe ASC")
	}
	// 컬럼 타입 처리
	for _, tuple := range req.Attributes {
		tuple.TypeId = req.TypeId
		switch tuple.Type {
		case metadata.MetadataSchemaAttribute_double_precision:
			tuple.TypeName = "double precision"
		case metadata.MetadataSchemaAttribute_text:
			if tuple.Length > 0 {
				tuple.TypeName = fmt.Sprintf("varchar(%d)", tuple.Length)
			} else {
				tuple.TypeName = "text"
			}
		default:
			tuple.TypeName = metadata.MetadataSchemaAttribute_Type_name[int32(tuple.Type)]
		}

		log.Debugf("Create attribute %q (%s) of %q", tuple.Attribute, tuple.TypeName, req.TypeId)
		if _, err := tx.ModelContext(ctx, tuple).Insert(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}

		columns = append(columns, fmt.Sprintf("%s %s NOT NULL", tuple.Attribute, tuple.TypeName))
	}
	columns = append(columns, "created_at timestamptz NOT NULL DEFAULT NOW()")

	// 센서 타입에 해당하는 테이블 생성
	for _, query := range []string{
		fmt.Sprintf("CREATE TABLE %q (%s)", req.TypeId, strings.Join(columns, ", ")),
		fmt.Sprintf("SELECT create_hypertable('%s', 'ts', chunk_time_interval => INTERVAL '1 week', if_not_exists => true)", req.TypeId),
		fmt.Sprintf("SELECT add_dimension('%s', 'site_id', number_partitions => 100, if_not_exists => true)", req.TypeId),
		fmt.Sprintf("CREATE UNIQUE INDEX IF NOT EXISTS %s_idx ON %s USING BTREE (%s)", req.TypeId, req.TypeId, strings.Join(indexColumn, ", ")),
	} {
		if _, err := tx.ExecContext(ctx, query); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	if err := sensorTypeQuery(ctx, conn).Where("type_id = ?", req.TypeId).Select(req); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return req, nil
}
