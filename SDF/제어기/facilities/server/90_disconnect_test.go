package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestDisconnect(t *testing.T) {
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			for _, dev := range testDevices {
				// 1번 센서 해제
				t.Run(dev.DeviceId, func(t *testing.T) {
					res, err := facilities.Client().Disconnect(context.Background(), &facilities.DisconnectRequest{
						FacilityId: suite.FacilityId,
						DeviceId:   dev.DeviceId,
						Modbus:     1,
					})
					assert.NoError(t, err)
					assert.NotNil(t, res)
				})

				// 전체 해제
				t.Run(dev.DeviceId, func(t *testing.T) {
					res, err := facilities.Client().Disconnect(context.Background(), &facilities.DisconnectRequest{
						FacilityId: suite.FacilityId,
						DeviceId:   dev.DeviceId,
					})
					assert.NoError(t, err)
					assert.NotNil(t, res)
				})

				// 연결되지 않은 장치 해제
				t.Run(dev.DeviceId, func(t *testing.T) {
					res, err := facilities.Client().Disconnect(context.Background(), &facilities.DisconnectRequest{
						FacilityId: suite.FacilityId,
						DeviceId:   dev.DeviceId,
					})
					assert.NoError(t, err)
					assert.NotNil(t, res)
				})
			}
		})
	}
}
