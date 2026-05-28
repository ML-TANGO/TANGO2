package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestDeleteSensor(t *testing.T) {
	ctx := context.Background()

	for _, suite := range testSuite {
		if suite.DeviceRole != devices.DeviceRole_NODE {
			continue
		}

		// 삭제
		t.Run(suite.DeviceId, func(t *testing.T) {
			for _, sensor := range suite.Sensors {
				t.Run(sensor.SensorId, func(t *testing.T) {
					res, err := devices.Client().DeleteSensor(ctx, &devices.DeleteSensorRequest{
						DeviceId: suite.DeviceId,
						SensorId: sensor.SensorId,
					})
					assert.NoError(t, err)
					assert.NotNil(t, res)
				})
			}
		})

		// 재삭제
		t.Run(suite.DeviceId, func(t *testing.T) {
			for _, sensor := range suite.Sensors {
				t.Run(sensor.SensorId, func(t *testing.T) {
					res, err := devices.Client().DeleteSensor(ctx, &devices.DeleteSensorRequest{
						DeviceId: suite.DeviceId,
						SensorId: sensor.SensorId,
					})
					assert.NoError(t, err)
					assert.NotNil(t, res)
				})
			}
		})
	}
}
