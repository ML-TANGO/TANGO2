package server

import (
	"testing"

	"context"
	"os"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestProducts(t *testing.T) {
	for _, suite := range testProductSuite {
		t.Run(suite.ModelNumber, func(t *testing.T) {
			res, err := facilities.Client().Products(context.Background(), &facilities.ProductRequest{
				ManufactureId: suite.ManufactureId,
				ModelNumber:   suite.ModelNumber,
			})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}

	os.Setenv("SECURE_MODE", "enable")
	defer os.Setenv("SECURE_MODE", "disable")

	// 인증 테스트
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().Products(sa, &facilities.ProductRequest{
				ManufactureId: suite.ManufactureId,
				ModelNumber:   suite.ModelNumber,
			})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}
}
