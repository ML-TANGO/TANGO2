package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/structpb"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestCreateProduct(t *testing.T) {
	testCases := []struct {
		desc     string
		args     *facilities.Product
		expected codes.Code
	}{
		{
			desc:     "빈 요청",
			args:     &facilities.Product{},
			expected: codes.InvalidArgument,
		},
		{
			desc: "모델 번호 누락",
			args: &facilities.Product{
				ManufactureId: testManufactureID,
				ProductName:   "테스트 제품",
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "성공 (제조사 생성 포함)",
			args: &facilities.Product{
				ManufactureId: testManufactureID,
				Manufacture: &structpb.Struct{Fields: map[string]*structpb.Value{
					"siteName": structpb.NewStringValue("테스트 제조사"),
				}},
				ModelNumber: fmt.Sprintf("p-%d-1", testTime.Unix()),
				ProductName: "테스트 제품 1",
			},
			expected: codes.OK,
		},
		{
			desc: "성공",
			args: &facilities.Product{
				ManufactureId: testManufactureID,
				ModelNumber:   fmt.Sprintf("p-%d-2", testTime.Unix()),
				ProductName:   "테스트 제품 2",
				Attributes: map[string]string{
					testAttributes[0]: "테스트 1",
					testAttributes[1]: "테스트 2",
					testAttributes[2]: "테스트 3",
				},
			},
			expected: codes.OK,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.desc, func(t *testing.T) {
			res, err := facilities.Client().CreateProduct(context.Background(), tc.args)
			if tc.expected == codes.OK {
				if assert.NoError(t, err) && assert.NotNil(t, res, "Request: %v", tc.args) {
					validateProduct(t, tc.args, res)
					testProductSuite = append(testProductSuite, res)
				}
			} else if assert.Error(t, err, "Request: %+v", tc.args) {
				assert.Equal(t, tc.expected, status.Code(err), err.Error())
			}
		})
	}
}

func validateProduct(t *testing.T, expected, actual *facilities.Product) {
	assert.Equal(t, expected.ManufactureId, actual.ManufactureId, "ManufactureId")
	assert.Equal(t, expected.ModelNumber, actual.ModelNumber, "ModelNumber")
	assert.Equal(t, expected.ProductName, actual.ProductName, "ProductName")
	assert.NotEmpty(t, actual.CreatedAt, "CreatedAt")
}
