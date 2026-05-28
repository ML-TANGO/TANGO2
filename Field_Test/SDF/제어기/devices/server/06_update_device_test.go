package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestUpdateDevice(t *testing.T) {
	ctx := context.Background()

	for _, suite := range testSuite {
		t.Run(fmt.Sprintf("수정사항 없이 요청 %s", suite.DeviceId), func(t *testing.T) {
			res, err := devices.Client().UpdateDevice(ctx, suite)
			if assert.Error(t, err) && assert.Nil(t, res) {
				assert.Equal(t, codes.InvalidArgument, status.Code(err))
			}
		})
	}

	for _, suite := range testSuite {
		changed := proto.Clone(suite).(*devices.Device)
		changed.DisplayName = "유효성 검사\n오류"
		t.Run(fmt.Sprintf("유효성 검사 오류 %s", changed.DeviceId), func(t *testing.T) {
			res, err := devices.Client().UpdateDevice(ctx, changed)
			if assert.Error(t, err) && assert.Nil(t, res) {
				assert.Equal(t, codes.InvalidArgument, status.Code(err))
			}
		})
	}

	// 장치 정보 변경
	for _, suite := range testSuite {
		changed := proto.Clone(suite).(*devices.Device)
		changed.DisplayName = ""
		changed.Description = "변경 테스트"
		t.Run(changed.DeviceId, func(t *testing.T) {
			res, err := devices.Client().UpdateDevice(ctx, changed)
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				validDevice(t, changed, res)
			}
		})
	}
}
