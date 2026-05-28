package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestSearchType(t *testing.T) {
	testCases := []struct {
		desc string
		args *devices.SearchTypeRequest
	}{
		{
			desc: "전체 조회",
			args: &devices.SearchTypeRequest{},
		},
		{
			desc: "전체 조회",
			args: &devices.SearchTypeRequest{
				TypeId: "temp_humi",
			},
		},
	}

	for k, v := range devices.SearchTypeRequest_Attribute_name {
		testCases = append(testCases, []struct {
			desc string
			args *devices.SearchTypeRequest
		}{
			{
				desc: fmt.Sprintf("응답 필드 선택 (%s)", v),
				args: &devices.SearchTypeRequest{
					Field: []devices.SearchTypeRequest_Attribute{(devices.SearchTypeRequest_Attribute)(k)},
				},
			},
			{
				desc: fmt.Sprintf("오름차순 정렬 (%s)", v),
				args: &devices.SearchTypeRequest{
					Asc: []devices.SearchTypeRequest_Attribute{(devices.SearchTypeRequest_Attribute)(k)},
				},
			},
			{
				desc: fmt.Sprintf("내림차순 정렬 (%s)", v),
				args: &devices.SearchTypeRequest{
					Desc: []devices.SearchTypeRequest_Attribute{(devices.SearchTypeRequest_Attribute)(k)},
				},
			},
		}...)
	}

	ctx := context.Background()
	for _, req := range testCases {
		t.Run(req.desc, func(t *testing.T) {
			res, err := devices.Client().SearchType(ctx, req.args)
			if assert.NoError(t, err) {
				assert.NotNil(t, res, "Request: %v", req)
			}
		})
	}
}
