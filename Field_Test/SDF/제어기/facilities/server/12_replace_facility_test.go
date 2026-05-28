package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestReplaceFacility(t *testing.T) {
	for i, suite := range testFacilitySuite {
		t.Run(fmt.Sprintf("변경 없이 요청 %d", i), func(t *testing.T) {
			res, err := facilities.Client().ReplaceFacility(context.Background(), suite)
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				validFacility(t, suite, res)
			}
		})
	}

	for _, suite := range testFacilitySuite {
		suite.FacilityName = "이름 변경 테스트"
		suite.SerialNumber = "일련번호변경"
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().ReplaceFacility(context.Background(), suite)
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				validFacility(t, suite, res)

			}
		})
	}
}
