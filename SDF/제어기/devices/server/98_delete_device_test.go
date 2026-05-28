package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestDeleteDevice(t *testing.T) {
	ctx := context.Background()

	for _, suite := range testSuite {
		t.Run(suite.DeviceId, func(t *testing.T) {
			res, err := devices.Client().DeleteDevice(ctx, &devices.DeviceRequest{DeviceId: suite.DeviceId})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}

	// 중복 삭제
	for _, suite := range testSuite {
		t.Run(suite.DeviceId, func(t *testing.T) {
			res, err := devices.Client().DeleteDevice(ctx, &devices.DeviceRequest{DeviceId: suite.DeviceId})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}
}
