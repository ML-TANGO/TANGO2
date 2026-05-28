package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestControlProduct(t *testing.T) {
	for _, suite := range testProductSuite {
		t.Run(suite.ModelNumber, func(t *testing.T) {
			// 제어 설정 조회
			res, err := facilities.Client().ControlProduct(context.Background(), &facilities.ControlProductRequest{
				ManufactureId: suite.ManufactureId,
				ModelNumber:   suite.ModelNumber,
			})
			assert.NoError(t, err)
			if assert.NotNil(t, res) {
				assert.GreaterOrEqual(t, len(res.Entities), 1)
				t.Logf("entities: %+v", res.Entities)
			}
		})
	}
}
