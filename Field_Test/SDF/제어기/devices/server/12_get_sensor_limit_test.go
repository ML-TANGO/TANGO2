package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestGetSensorLimit(t *testing.T) {
	ctx := context.Background()

	// 임계치 조회
	for _, suite := range testSuite {
		t.Run(suite.DeviceId, func(t *testing.T) {
			for _, sensor := range suite.Sensors {
				if sensor.SensorType != testTypeSuite[0].TypeId {
					continue
				}
				t.Run(sensor.SensorId, func(t *testing.T) {
					res, err := devices.Client().GetSensorLimit(ctx, &devices.GetLimitRequest{
						DeviceId: suite.DeviceId,
						Channel:  sensor.ChannelId,
					})
					assert.NoError(t, err)
					assert.NotNil(t, res)
				})
			}
		})
	}

	// 존재하지 않는 장치에 대한 임계치 조회
	for _, suite := range testSuite {
		t.Run(suite.DeviceId, func(t *testing.T) {
			for _, sensor := range suite.Sensors {
				if sensor.SensorType != testTypeSuite[0].TypeId {
					continue
				}
				t.Run(sensor.SensorId, func(t *testing.T) {
					res, err := devices.Client().GetSensorLimit(ctx, &devices.GetLimitRequest{
						DeviceId: suite.DeviceId,
						Channel:  101,
					})
					if assert.Nil(t, res) && assert.Error(t, err) {
						assert.Equal(t, codes.NotFound, status.Code(err))
					}
				})
			}
		})
	}
}
