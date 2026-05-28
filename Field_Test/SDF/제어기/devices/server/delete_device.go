package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/types/known/emptypb"

	"gitlab.suredatalab.kr/beymons/devices"
)

// DeleteDevice - 장치 삭제
func (s DevicesServer) DeleteDevice(ctx context.Context, req *devices.DeviceRequest) (*emptypb.Empty, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// TODO: DeviceConfigLink 정리
	// TODO: DeviceLink 정리? or 실패?

	res, err := tx.ModelContext(ctx, &devices.Device{DeviceId: req.DeviceId}).WherePK().Delete()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}
	if res.RowsAffected() == 0 {
		return &emptypb.Empty{}, nil
	}
	log.Debugf("Delete device %q", req.DeviceId)

	// 사용자 정보
	claims, err := auth.GetClaim(ctx)
	if err != nil {
		return nil, err
	}

	// 이력 기록
	if err := writeHistory(ctx, tx, req.DeviceId, claims.UserID, devices.DeviceHistory_DELETE, nil); err != nil {
		return nil, err
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	log.Infof("Device %q is successfully deleted", req.DeviceId)
	return &emptypb.Empty{}, nil
}
