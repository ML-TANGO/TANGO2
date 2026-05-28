package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestDeleteSensorLimit(t *testing.T) {
	ctx := context.Background()

	// 임계치 설정
	for _, suite := range testSuite {
		t.Run(suite.DeviceId, func(t *testing.T) {
			for _, sensor := range suite.Sensors {
				if sensor.SensorType != testTypeSuite[0].TypeId {
					continue
				}
				t.Run(sensor.SensorId, func(t *testing.T) {
					res, err := devices.Client().DeleteSensorLimit(ctx, &devices.DeleteLimitRequest{
						DeviceId:  suite.DeviceId,
						Channel:   sensor.ChannelId,
						Attribute: testTypeSuite[0].Attributes[0].Attribute,
					})
					assert.NoError(t, err)
					assert.NotNil(t, res)
				})
			}
		})
	}
}
