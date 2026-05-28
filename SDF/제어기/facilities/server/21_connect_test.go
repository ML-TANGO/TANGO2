package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestConnect(t *testing.T) {
	for i, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			deviceID := "TESTNOTEXISTS"
			// 없는 장치 연결
			t.Run(deviceID, func(t *testing.T) {
				res, err := facilities.Client().Connect(context.Background(), &facilities.ConnectRequest{
					FacilityId: suite.FacilityId,
					Devices: []*facilities.ConnectRequest_Device{
						{
							DeviceId: deviceID,
							Modbus:   1,
						},
					},
				})
				assert.Nil(t, res)
				if assert.Error(t, err) {
					assert.Equal(t, codes.NotFound, status.Code(err))
				}
			})

			dev, err := createTestNode(fmt.Sprint(i))
			if !assert.NoError(t, err) {
				t.FailNow()
			}

			deviceID = dev.GetDeviceId()

			// 장치 연결
			t.Run(deviceID, func(t *testing.T) {
				// 없는 센서 연결
				t.Run("100", func(t *testing.T) {
					res, err := facilities.Client().Connect(context.Background(), &facilities.ConnectRequest{
						FacilityId: suite.FacilityId,
						Devices: []*facilities.ConnectRequest_Device{
							{
								DeviceId:    deviceID,
								Modbus:      100,
								Description: "존재하지 않는 센서",
							},
						},
					})
					assert.Nil(t, res)
					if assert.Error(t, err) {
						assert.Equal(t, codes.NotFound, status.Code(err))
					}
				})

				res, err := facilities.Client().Connect(context.Background(), &facilities.ConnectRequest{
					FacilityId: suite.FacilityId,
					Devices: []*facilities.ConnectRequest_Device{
						{
							DeviceId:    deviceID,
							Modbus:      1,
							Description: "연결 테스트",
						},
					},
				})
				if assert.NoError(t, err) && assert.NotNil(t, res) {
					assert.GreaterOrEqual(t, len(res.Entities), 1)
				}
			})

			// 이미 연결한 장치 재연결
			t.Run(deviceID, func(t *testing.T) {
				res, err := facilities.Client().Connect(context.Background(), &facilities.ConnectRequest{
					FacilityId: suite.FacilityId,
					Devices: []*facilities.ConnectRequest_Device{
						{
							DeviceId: deviceID,
							Modbus:   1,
						},
					},
				})
				assert.Nil(t, res)
				if assert.Error(t, err) {
					assert.Equal(t, codes.AlreadyExists, status.Code(err))
				}
			})
		})
	}
}
