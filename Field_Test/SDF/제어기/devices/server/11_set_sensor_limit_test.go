package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestSetSensorLimit(t *testing.T) {
	testCases := []struct {
		desc     string
		args     *devices.SetLimitRequest
		expected codes.Code
	}{
		{
			desc:     "필수 입력 항목 누락",
			args:     &devices.SetLimitRequest{},
			expected: codes.InvalidArgument,
		},
		{
			desc: "정상값 범위 오류",
			args: &devices.SetLimitRequest{
				DeviceId:   "test-device",
				Channel:    1,
				Attribute:  "temp",
				NormalMin:  10,
				NormalMax:  0,
				CautionMin: -10,
				CautionMax: 20,
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "주의값 범위 오류",
			args: &devices.SetLimitRequest{
				DeviceId:   "test-device",
				Channel:    1,
				Attribute:  "temp",
				NormalMin:  0,
				NormalMax:  10,
				CautionMin: 20,
				CautionMax: -20,
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "하한값 범위 오류",
			args: &devices.SetLimitRequest{
				DeviceId:   "test-device",
				Channel:    1,
				Attribute:  "temp",
				NormalMin:  0,
				NormalMax:  20,
				CautionMin: 10,
				CautionMax: 30,
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "상한값 범위 오류",
			args: &devices.SetLimitRequest{
				DeviceId:   "test-device",
				Channel:    1,
				Attribute:  "temp",
				NormalMin:  0,
				NormalMax:  20,
				CautionMin: -10,
				CautionMax: 10,
			},
			expected: codes.InvalidArgument,
		},
	}

	ctx := context.Background()
	for _, suite := range testCases {
		t.Run(suite.desc, func(t *testing.T) {
			_, err := devices.Client().SetSensorLimit(ctx, suite.args)
			if assert.Error(t, err) {
				assert.Equal(t, suite.expected, status.Code(err))
			}
		})
	}

	// 임계치 설정
	for _, suite := range testSuite {
		t.Run(suite.DeviceId, func(t *testing.T) {
			for _, sensor := range suite.Sensors {
				if sensor.SensorType != testTypeSuite[0].TypeId {
					continue
				}
				t.Run(sensor.SensorId, func(t *testing.T) {
					req := &devices.SetLimitRequest{
						DeviceId:   suite.DeviceId,
						Channel:    sensor.ChannelId,
						Attribute:  testTypeSuite[0].Attributes[0].Attribute,
						NormalMin:  0,
						NormalMax:  10,
						CautionMin: -10,
						CautionMax: 20,
					}
					res, err := devices.Client().SetSensorLimit(ctx, req)
					if assert.NoError(t, err) && assert.NotNil(t, res) {
						assert.Equal(t, req.Channel, res.Channel)
						assert.Equal(t, req.Attribute, res.Attribute)
						assert.Equal(t, req.NormalMin, res.NormalMin)
						assert.Equal(t, req.NormalMax, res.NormalMax)
						assert.Equal(t, req.CautionMin, res.CautionMin)
						assert.Equal(t, req.CautionMax, res.CautionMax)
						assert.NotNil(t, res.CreatedAt)
					}
				})
			}
		})
	}
}
