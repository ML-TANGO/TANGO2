package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestSearch(t *testing.T) {
	testCases := []struct {
		desc string
		args *devices.SearchRequest
	}{
		{
			desc: "전체 조회",
			args: &devices.SearchRequest{},
		},
		{
			desc: "전체 검색",
			args: &devices.SearchRequest{
				Search: "test",
			},
		},
		{
			desc: "사이트 검색",
			args: &devices.SearchRequest{
				SiteId: "test",
			},
		},
		{
			desc: "센서 타입",
			args: &devices.SearchRequest{
				SensorType: []string{"temperature"},
			},
		},
		{
			desc: "장치 구분",
			args: &devices.SearchRequest{
				Role: []devices.DeviceRole{devices.DeviceRole_NODE},
			},
		},
		{
			desc: "장치 상태",
			args: &devices.SearchRequest{
				Status: []devices.DeviceStatus{devices.DeviceStatus_NORMAL},
			},
		},
	}

	for k, v := range devices.Attribute_name {
		testCases = append(testCases, []struct {
			desc string
			args *devices.SearchRequest
		}{
			{
				desc: fmt.Sprintf("응답 필드 선택 (%s)", v),
				args: &devices.SearchRequest{
					Field: []devices.Attribute{(devices.Attribute)(k)},
				},
			},
		}...)
	}

	ctx := context.Background()
	for _, req := range testCases {
		t.Run(req.desc, func(t *testing.T) {
			res, err := devices.Client().Search(ctx, req.args)
			if assert.NoError(t, err) {
				assert.NotNil(t, res, "Request: %v", req)
			}
			for k, v := range devices.SearchRequest_Order_value {
				req.args.Order = []devices.SearchRequest_Order{
					devices.SearchRequest_Order(v),
				}
				t.Run(k, func(t *testing.T) {
					res, err := devices.Client().Search(ctx, req.args)
					if assert.NoError(t, err) {
						assert.NotNil(t, res, "Request: %v", req)
					}
				})
			}
		})
	}
}
