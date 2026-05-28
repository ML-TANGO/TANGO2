package server

import (
	"testing"

	"context"
	"fmt"
	"time"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/devices"
)

var (
	testSuite []*devices.Device
)

func TestCreateDevice(t *testing.T) {
	if !assert.Greater(t, len(testTypeSuite), 0) {
		t.FailNow()
	}

	testCases := []struct {
		desc     string
		args     *devices.Device
		expected codes.Code
	}{
		{
			desc:     "필수 입력 항목 누락",
			args:     &devices.Device{},
			expected: codes.InvalidArgument,
		},
		{
			desc: "유효성 검사 오류 (device_id)",
			args: &devices.Device{
				DeviceId:    "한글 ID",
				DisplayName: "한글\nID",
				DeviceRole:  devices.DeviceRole_GATEWAY,
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "GW에 센서 연결",
			args: &devices.Device{
				DeviceId:    fmt.Sprintf("g-t%d", time.Now().Unix()),
				DisplayName: "TEST GW",
				DeviceRole:  devices.DeviceRole_GATEWAY,
				Sensors: []*devices.Sensor{
					{
						ChannelId:  1,
						SensorType: testTypeSuite[0].TypeId,
					},
				},
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "GW 생성",
			args: &devices.Device{
				DeviceId:    fmt.Sprintf("g-t%d", time.Now().Unix()),
				DisplayName: "TEST GW",
				DeviceRole:  devices.DeviceRole_GATEWAY,
			},
			expected: codes.OK,
		},
		{
			desc: "채널 중복 오류",
			args: &devices.Device{
				DeviceId:    fmt.Sprintf("n-t%d", time.Now().Unix()),
				DisplayName: "TEST NODE",
				DeviceRole:  devices.DeviceRole_NODE,
				Sensors: []*devices.Sensor{
					{
						ChannelId:  1,
						SensorType: testTypeSuite[0].TypeId,
					},
					{
						ChannelId:  1,
						SensorType: testTypeSuite[0].TypeId,
					},
				},
			},
			expected: codes.AlreadyExists,
		},
		{
			desc: "NODE 생성",
			args: &devices.Device{
				DeviceId:    fmt.Sprintf("n-t%d", time.Now().Unix()),
				DisplayName: "TEST NODE",
				DeviceRole:  devices.DeviceRole_NODE,
				Sensors: []*devices.Sensor{
					{
						ChannelId:  1,
						SensorType: testTypeSuite[0].TypeId,
					},
					{
						ChannelId:  2,
						SensorType: testAgsMotorType,
					},
				},
			},
			expected: codes.OK,
		},
	}

	ctx := context.Background()
	for _, suite := range testCases {
		t.Run(suite.desc, func(t *testing.T) {
			res, err := devices.Client().CreateDevice(ctx, suite.args)
			if suite.expected == codes.OK {
				if assert.NoError(t, err) && assert.NotNil(t, res, "Request: %+v", suite.args) {
					testSuite = append(testSuite, res)
					validDevice(t, suite.args, res)
				}
			} else if assert.Error(t, err, "Request: %+v", suite.args) {
				assert.Equal(t, suite.expected, status.Code(err), err.Error())
				t.Log(err)
			}
		})
	}

	// 센서 타입별로 장치 생성
	for i, suite := range testTypeSuite {
		req := &devices.Device{
			DeviceId:    fmt.Sprintf("T%d-%d", time.Now().Unix(), i),
			DisplayName: "TEST NODE",
			DeviceRole:  devices.DeviceRole_NODE,
			Sensors: []*devices.Sensor{
				{
					ChannelId:  1,
					SensorType: suite.TypeId,
				},
			},
		}
		res, err := devices.Client().CreateDevice(ctx, req)
		if assert.NoError(t, err) && assert.NotNil(t, res, "Request: %+v", req) {
			testSuite = append(testSuite, res)
			validDevice(t, req, res)
		}
	}

	// 중복 생성
	for _, suite := range testSuite {
		t.Run(fmt.Sprintf("중복 %s", suite.DeviceId), func(t *testing.T) {
			res, err := devices.Client().CreateDevice(ctx, suite)
			assert.Nil(t, res)
			if assert.Error(t, err) {
				assert.Equal(t, status.Code(err), codes.AlreadyExists, err.Error())
			}
		})
	}
}

// 장치 정보 검증
func validDevice(t *testing.T, prev, device *devices.Device) {
	assert.Equal(t, prev.DeviceId, device.DeviceId)
	assert.Equal(t, prev.DisplayName, device.DisplayName)
	assert.Equal(t, prev.Description, device.Description)
	assert.Equal(t, prev.DeviceRole, device.DeviceRole)
	assert.NotEmpty(t, device.CreatedAt)
	assert.NotEmpty(t, device.UpdatedAt)

	if assert.Equal(t, len(prev.Sensors), len(device.Sensors)) {
		origin := make(map[uint32]*devices.Sensor)
		for _, sensor := range prev.Sensors {
			origin[sensor.ChannelId] = sensor
		}

		for _, sensor := range device.Sensors {
			originSensor, ok := origin[sensor.ChannelId]
			if assert.True(t, ok) {
				assert.NotEmpty(t, sensor.SensorId)
				assert.Equal(t, prev.DeviceId, sensor.DeviceId, "DeviceId")
				assert.Equal(t, originSensor.ChannelId, sensor.ChannelId, "ChannelId")
				assert.Equal(t, originSensor.SensorType, sensor.SensorType, "SensorType")
				assert.Equal(t, originSensor.DisplayName, sensor.DisplayName, "DisplayName")
				assert.Equal(t, originSensor.Description, sensor.Description, "Description")
			}
		}
	}
}
