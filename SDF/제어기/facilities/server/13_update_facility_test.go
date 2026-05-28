package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestUpdateFacility(t *testing.T) {
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().UpdateFacility(context.Background(), &facilities.UpdateFacilityRequest{
				FacilityId: suite.FacilityId,
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

	for _, suite := range testFacilitySuite {
		changed := map[string]string{
			testAttributes[0]: "변경 테스트 1",
			testAttributes[1]: "변경 테스트 2",
		}
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().UpdateFacility(context.Background(), &facilities.UpdateFacilityRequest{
				FacilityId: suite.FacilityId,
				Payload:    changed,
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
