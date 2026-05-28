package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestDeleteProduct(t *testing.T) {
	// 삭제
	for _, suite := range testProductSuite {
		t.Run(suite.ModelNumber, func(t *testing.T) {
			res, err := facilities.Client().DeleteProduct(context.Background(), &facilities.ProductRequest{
				ManufactureId: suite.ManufactureId,
				ModelNumber:   suite.ModelNumber,
			})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}

	// 재삭제
	for _, suite := range testProductSuite {
		t.Run(suite.ModelNumber, func(t *testing.T) {
			res, err := facilities.Client().DeleteProduct(context.Background(), &facilities.ProductRequest{
				ManufactureId: suite.ManufactureId,
				ModelNumber:   suite.ModelNumber,
			})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}
}
