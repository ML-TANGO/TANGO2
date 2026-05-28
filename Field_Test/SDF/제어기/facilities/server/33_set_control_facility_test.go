package server

import (
	"fmt"
	"testing"

	"context"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/devices"
	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestSetControlFacility(t *testing.T) {
	testCases := []struct {
		desc     string
		args     *facilities.SetControlFacilityRequest
		expected codes.Code
	}{
		{
			desc:     "빈 요청",
			args:     &facilities.SetControlFacilityRequest{},
			expected: codes.InvalidArgument,
		},
		{
			desc: "설비 고유 제어 설정 추가",
			args: &facilities.SetControlFacilityRequest{
				Payload: &facilities.SetControlFacilityRequest_Create{
					Create: &facilities.SetControlFacilityRequest_Custom{
						ControlName: "1중 측창",
						Modbus:      1,
						SensorType:  testSensorType,
						Command:     "set_config_req",
						Payload:     `{"1": {{.ratio}}, "2": {{.ratio}}}`,
					},
				},
			},
			expected: codes.OK,
		},
	}

	// 장치 생성 및 출고
	devGreen, err := createTestNode(beymonsGreen)
	if !assert.NoError(t, err) {
		t.FailNow()
	}

	var facilityControls []*facilities.FacilityControl
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			// 설비에서 사용할 장치 조회
			dev, err := facilities.Client().Devices(context.Background(), &devices.SearchRequest{
				FacilityId: suite.FacilityId,
				Order:      []devices.SearchRequest_Order{devices.SearchRequest_device_id_asc},
			})
			if !assert.NoError(t, err) || !assert.NotNil(t, dev) || !assert.GreaterOrEqual(t, len(dev.Entities), 1) {
				t.Fail()
				return
			}

			for _, tc := range testCases {
				t.Run(tc.desc, func(t *testing.T) {
					tc.args.FacilityId = suite.FacilityId

					req := &facilities.SetControlFacilityRequest{
						FacilityId: suite.FacilityId,
					}

					var targetDevice string
					switch tc.args.Payload.(type) {
					case *facilities.SetControlFacilityRequest_Create:
						payload := tc.args.GetCreate()
						payload.DeviceId = dev.Entities[0].DeviceId
						targetDevice = payload.DeviceId
						req.Payload = &facilities.SetControlFacilityRequest_Create{Create: payload}
					}

					res, err := facilities.Client().SetControlFacility(context.Background(), req)
					if tc.expected == codes.OK {
						if assert.NoError(t, err) && assert.NotNil(t, res, "Request: %v", req) {
							assert.NotEmpty(t, res.ControlId)
							assert.Equal(t, tc.args.FacilityId, res.FacilityId)
							assert.NotEmpty(t, res.UpdatedAt)

							switch tc.args.Payload.(type) {
							case *facilities.SetControlFacilityRequest_Create:
								origin := tc.args.GetCreate()
								assert.Equal(t, targetDevice, res.DeviceId)
								assert.Equal(t, origin.Modbus, res.Modbus)
								assert.Equal(t, origin.SensorType, res.SensorType)
								assert.Equal(t, origin.ControlName, res.ControlName)
								assert.Equal(t, origin.Command, res.Command)
								assert.Equal(t, origin.Payload, res.Payload)
							}
							facilityControls = append(facilityControls, res)
						}
					} else if assert.Error(t, err, "Request: %+v", tc.args) {
						assert.Equal(t, tc.expected, status.Code(err), err.Error())
					}
				})
			}

			// 센서 타입별 테스트
			for _, typeID := range []string{"agsmotor_green"} {
				facilityControls = append(facilityControls, testRunSensorType(t, suite.FacilityId, typeID, dev.Entities[0].DeviceId)...)
			}
		})
	}

	// 업데이트 테스트
	for i, config := range facilityControls {
		t.Run(fmt.Sprintf("%s/controls/%s", config.FacilityId, config.ControlId), func(t *testing.T) {
			req := &facilities.SetControlFacilityRequest{
				FacilityId: config.FacilityId,
				ControlId:  config.ControlId,
				Payload: &facilities.SetControlFacilityRequest_Update{
					Update: &facilities.SetControlFacilityRequest_Custom{
						ControlName: fmt.Sprintf("%d번 제어 설정 변경", config.Modbus),
						DeviceId:    devGreen.DeviceId,
						SensorType:  "agsmotor_green",
						Modbus:      uint32(i) + 1,
						Command:     "set_agsmotor_operation_req",
						Payload:     `{"1": {{.ratio}}}`,
					},
				},
			}
			res, err := facilities.Client().SetControlFacility(context.Background(), req)
			if assert.NoError(t, err) && assert.NotNil(t, res, "Request: %v", req) {
				origin := req.GetUpdate()
				assert.Equal(t, devGreen.DeviceId, res.DeviceId)
				assert.Equal(t, origin.Modbus, res.Modbus)
				assert.Equal(t, origin.SensorType, res.SensorType)
				assert.Equal(t, origin.ControlName, res.ControlName)
				assert.Equal(t, origin.Command, res.Command)
				assert.Equal(t, origin.Payload, res.Payload)
				facilityControls = append(facilityControls, res)
			}
		})
	}
}

func testRunSensorType(t *testing.T, facilityID, sensorType, deviceID string) (resp []*facilities.FacilityControl) {
	t.Run(sensorType, func(t *testing.T) {
		testRun := false
		// 설비 설정 조회
		list, err := facilities.Client().ControlFacility(context.Background(), &facilities.ControlFacilityRequest{
			FacilityId: facilityID,
		})
		if !assert.NoError(t, err) && !assert.NotNil(t, list) {
			t.FailNow()
		}

		for i, config := range list.Entities {
			if len(config.ControlId) > 0 || len(config.PControlId) == 0 || config.SensorType != sensorType {
				continue
			}

			testRun = true
			t.Run(config.PControlId, func(t *testing.T) {
				req := &facilities.SetControlFacilityRequest{
					FacilityId: facilityID,
					Payload: &facilities.SetControlFacilityRequest_Replace_{
						Replace: &facilities.SetControlFacilityRequest_Replace{
							PControlId:  config.PControlId,
							ControlName: fmt.Sprintf("%d번 제어 설정", i),
							DeviceId:    deviceID,
							Modbus:      2,
							Command:     "set_agsmotor_op_req",
							Payload:     `{"1": {{.ratio}}, "2": {{.ratio}}}`,
						},
					},
				}
				res, err := facilities.Client().SetControlFacility(context.Background(), req)
				if assert.NoError(t, err) && assert.NotNil(t, res, "Request: %v", req) {
					origin := req.GetReplace()
					assert.Equal(t, deviceID, res.DeviceId)
					assert.Equal(t, origin.Modbus, res.Modbus)
					assert.Equal(t, config.SensorType, res.SensorType)
					assert.Equal(t, origin.ControlName, res.ControlName)
					assert.Equal(t, origin.Command, res.Command)
					assert.Equal(t, origin.Payload, res.Payload)
					resp = append(resp, res)
				}
			})
		}
		assert.True(t, testRun)
	})

	return
}
