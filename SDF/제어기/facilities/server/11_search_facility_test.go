package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestSearchFacility(t *testing.T) {
	testCases := []struct {
		desc string
		args *facilities.SearchFacilityRequest
	}{
		{
			desc: "전체 조회",
			args: &facilities.SearchFacilityRequest{},
		},
		{
			desc: "전체 검색",
			args: &facilities.SearchFacilityRequest{Search: "test"},
		},
		{
			desc: "응답 수 제한",
			args: &facilities.SearchFacilityRequest{Limit: 1},
		},
		{
			desc: "설비명으로 검색",
			args: &facilities.SearchFacilityRequest{Name: "test"},
		},
		{
			desc: "고객 ID로 필터링",
			args: &facilities.SearchFacilityRequest{SiteId: testSiteID},
		},
		{
			desc: "제조사 ID로 필터링",
			args: &facilities.SearchFacilityRequest{ManufactureId: []string{testManufactureID, "m.test-124"}},
		},
		{
			desc: "모델 번호로 검색",
			args: &facilities.SearchFacilityRequest{Model: "test"},
		},
		{
			desc: "일련 번호로 검색",
			args: &facilities.SearchFacilityRequest{Sn: "test"},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.desc, func(t *testing.T) {
			res, err := facilities.Client().SearchFacility(context.Background(), tc.args)
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})

		// 정렬 테스트
		for k, v := range facilities.SearchFacilityRequest_Order_value {
			req := proto.Clone(tc.args).(*facilities.SearchFacilityRequest)
			req.Order = []facilities.SearchFacilityRequest_Order{
				facilities.SearchFacilityRequest_Order(v),
			}
			t.Run(k, func(t *testing.T) {
				res, err := facilities.Client().SearchFacility(context.Background(), req)
				assert.NoError(t, err)
				assert.NotNil(t, res)

			})
		}
	}
}
