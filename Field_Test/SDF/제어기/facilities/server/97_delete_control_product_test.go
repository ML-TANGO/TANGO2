package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestDeleteControlProduct(t *testing.T) {
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

			for _, control := range list.Entities {
				t.Run(control.ControlId, func(t *testing.T) {
					res, err := facilities.Client().DeleteControlProduct(context.Background(), &facilities.ControlProductRequest{
						ManufactureId: suite.ManufactureId,
						ModelNumber:   suite.ModelNumber,
						ControlId:     control.ControlId,
					})
					assert.NoError(t, err)
					assert.NotNil(t, res)
				})
			}
		})
	}
}
