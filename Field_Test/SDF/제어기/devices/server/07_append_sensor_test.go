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

func TestAppendSensor(t *testing.T) {
	ctx := context.Background()

	for _, suite := range testSuite {
		if suite.DeviceRole != devices.DeviceRole_NODE {
			continue
		}

		// 중복 생성 테스트
		t.Run(fmt.Sprintf("%s/sensors", suite.DeviceId), func(t *testing.T) {
			res, err := devices.Client().AppendSensor(ctx, &devices.Sensor{
				DeviceId:   suite.DeviceId,
				ChannelId:  1,
				SensorType: testTypeSuite[0].TypeId,
			})
			assert.Nil(t, res)
			if assert.Error(t, err) {
				assert.Equal(t, status.Code(err), codes.AlreadyExists, err.Error())
			}
		})

		// 센서 정보 수정
		for _, sensor := range suite.Sensors {

			sensor.DisplayName = "이름 변경"
			sensor.Description = "설명 수정 테스트"
			t.Run(fmt.Sprintf("%s/sensors/%s", suite.DeviceId, sensor.SensorId), func(t *testing.T) {
				res, err := devices.Client().AppendSensor(ctx, sensor)
				assert.NotNil(t, res)
				assert.NoError(t, err)
			})
		}

		// 센서 추가
		t.Run(fmt.Sprintf("%s/sensors", suite.DeviceId), func(t *testing.T) {
			res, err := devices.Client().AppendSensor(ctx, &devices.Sensor{
				DeviceId:    suite.DeviceId,
				ChannelId:   uint32(len(suite.Sensors)) + 1,
				SensorType:  testTypeSuite[0].TypeId,
				Description: "센서 추가 테스트",
			})
			assert.NotNil(t, res)
			assert.NoError(t, err)
		})
	}
}
