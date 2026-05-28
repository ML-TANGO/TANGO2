package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestCreateControlProduct(t *testing.T) {
	testCases := []struct {
		desc     string
		args     *facilities.ProductControl
		expected codes.Code
	}{
		{
			desc:     "빈 요청",
			args:     &facilities.ProductControl{},
			expected: codes.InvalidArgument,
		},
		{
			desc: "센서 타입 필드 유효성 검사 오류",
			args: &facilities.ProductControl{
				ControlName: "1중 좌측 측창",
				Modbus:      1,
				SensorType:  "agsmotor green",
				Command:     "set_agsmotor_operation_req",
				Payload:     `{"1": {{.ratio}}}`,
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "센서 타입 필드 유효성 검사 오류",
			args: &facilities.ProductControl{
				ControlName: "1중 좌측 측창",
				Modbus:      1,
				SensorType:  "agsmotor_green",
				Command:     "set_agsmotor operation_req",
				Payload:     `{"1": {{.ratio}}}`,
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "성공",
			args: &facilities.ProductControl{
				ControlName: "1중 좌측 측창",
				Modbus:      1,
				SensorType:  "agsmotor_green",
				Command:     "set_agsmotor_req",
				Payload:     `{"1": {{.ratio}}}`,
			},
			expected: codes.OK,
		},
	}

	for _, suite := range testProductSuite {
		t.Run(suite.ModelNumber, func(t *testing.T) {
			for _, tc := range testCases {
				t.Run(tc.desc, func(t *testing.T) {
					tc.args.ManufactureId = suite.ManufactureId
					tc.args.ModelNumber = suite.ModelNumber
					res, err := facilities.Client().CreateControlProduct(context.Background(), tc.args)
					if tc.expected == codes.OK {
						if assert.NoError(t, err) && assert.NotNil(t, res, "Request: %v", tc.args) {
							assert.NotEmpty(t, res.ControlId)
							assert.Equal(t, tc.args.ManufactureId, res.ManufactureId)
							assert.Equal(t, tc.args.ModelNumber, res.ModelNumber)
							assert.Equal(t, tc.args.Modbus, res.Modbus)
							assert.Equal(t, tc.args.SensorType, res.SensorType)
							assert.Equal(t, tc.args.ControlName, res.ControlName)
							assert.Equal(t, tc.args.Command, res.Command)
							assert.Equal(t, tc.args.Payload, res.Payload)
							assert.NotEmpty(t, res.UpdatedAt)
						}
					} else if assert.Error(t, err, "Request: %+v", tc.args) {
						assert.Equal(t, tc.expected, status.Code(err), err.Error())
					}
				})
			}
		})
	}
}
