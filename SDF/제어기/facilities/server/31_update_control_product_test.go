package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestUpdateControlProduct(t *testing.T) {
	for _, suite := range testProductSuite {
		t.Run(suite.ModelNumber, func(t *testing.T) {
			// 제어 설정 조회
			list, err := facilities.Client().ControlProduct(context.Background(), &facilities.ControlProductRequest{
				ManufactureId: suite.ManufactureId,
				ModelNumber:   suite.ModelNumber,
			})
			if !assert.NoError(t, err) && !assert.NotNil(t, list) {
				t.FailNow()
			}

			// 업데이트 테스트
			for _, control := range list.Entities {
				t.Run(control.ControlId, func(t *testing.T) {
					req := &facilities.UpdateControlProductRequest{
						ManufactureId: suite.ManufactureId,
						ModelNumber:   suite.ModelNumber,
						ControlId:     control.ControlId,
						SensorType:    control.SensorType,
						Command:       control.Command,
						Payload:       control.Payload,
					}

					// 센서 타입에 따라 제어 명령 수정
					switch control.SensorType {
					case "agsmotor_green":
						req.Command = "set_agsmotor_operation_req"
					}

					res, err := facilities.Client().UpdateControlProduct(context.Background(), req)
					if assert.NoError(t, err) && assert.NotNil(t, res) {
						assert.Equal(t, req.Command, res.Command)
						assert.Greater(t, res.UpdatedAt.AsTime().UnixNano(), control.UpdatedAt.AsTime().UnixNano())
					}
				})
			}
		})
	}
}
