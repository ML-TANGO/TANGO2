package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestSearchProduct(t *testing.T) {
	testCases := []struct {
		desc string
		args *facilities.SearchProductRequest
	}{
		{
			desc: "전체 조회",
			args: &facilities.SearchProductRequest{},
		},
		{
			desc: "전체 검색",
			args: &facilities.SearchProductRequest{Search: "test"},
		},
		{
			desc: "제조사 ID로 필터링",
			args: &facilities.SearchProductRequest{
				ManufactureId: testManufactureID,
			},
		},
		{
			desc: "모델 번호로 필터링",
			args: &facilities.SearchProductRequest{
				Model: "test",
			},
		},
		{
			desc: "제품명 검색",
			args: &facilities.SearchProductRequest{
				Name: "test",
			},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.desc, func(t *testing.T) {
			res, err := facilities.Client().SearchProduct(context.Background(), tc.args)
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})

		// 정렬 테스트
		for k, v := range facilities.SearchProductRequest_Order_value {
			req := proto.Clone(tc.args).(*facilities.SearchProductRequest)
			req.Order = []facilities.SearchProductRequest_Order{
				facilities.SearchProductRequest_Order(v),
			}
			t.Run(k, func(t *testing.T) {
				res, err := facilities.Client().SearchProduct(context.Background(), req)
				assert.NoError(t, err)
				assert.NotNil(t, res)

			})
		}
	}
}
