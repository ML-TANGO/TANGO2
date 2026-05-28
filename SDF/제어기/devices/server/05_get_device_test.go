package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestGetDevice(t *testing.T) {
	for _, suite := range testSuite {
		t.Run(suite.DeviceId, func(t *testing.T) {
			res, err := devices.Client().GetDevice(context.Background(), &devices.DeviceRequest{DeviceId: suite.DeviceId})
			assert.NoError(t, err)
			if assert.NotNil(t, res) {
				suite.Sensors = res.Device.Sensors
			}
		})
	}

	// 존재하지 않는 장치 조회
	for _, suite := range testSuite {
		deviceID := fmt.Sprintf("%sx", suite.DeviceId)
		t.Run(deviceID, func(t *testing.T) {
			res, err := devices.Client().GetDevice(context.Background(), &devices.DeviceRequest{DeviceId: deviceID})
			assert.Nil(t, res)
			if assert.Error(t, err) {
				assert.Equal(t, status.Code(err), codes.NotFound, err.Error())
			}
		})
	}
}
