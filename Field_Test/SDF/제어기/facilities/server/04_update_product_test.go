package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestUpdateProduct(t *testing.T) {
	for _, suite := range testProductSuite {
		t.Run(suite.ModelNumber, func(t *testing.T) {
			res, err := facilities.Client().UpdateProduct(context.Background(), &facilities.UpdateProductRequest{
				ManufactureId: suite.ManufactureId,
				ModelNumber:   suite.ModelNumber,
				Payload: map[string]string{
					"not_exist_1": "변경 테스트 1",
					"not_exist_2": "변경 테스트 2",
					"not_exist_3": "변경 테스트 3",
				},
			})
			assert.Nil(t, res)
			if assert.Error(t, err) {
				assert.Equal(t, codes.InvalidArgument, status.Code(err))
			}
		})
	}

	for _, suite := range testProductSuite {
		changed := map[string]string{
			testAttributes[0]: "변경 테스트 1",
			testAttributes[1]: "변경 테스트 2",
		}
		t.Run(suite.ModelNumber, func(t *testing.T) {
			res, err := facilities.Client().UpdateProduct(context.Background(), &facilities.UpdateProductRequest{
				ManufactureId: suite.ManufactureId,
				ModelNumber:   suite.ModelNumber,
				Payload:       changed,
			})
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				suite.Attributes = changed
				for k, v := range changed {
					result, ok := res.Attributes[k]
					assert.True(t, ok)
					assert.Equal(t, v, result)
				}
			}
		})
	}
}
