package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"
	"google.golang.org/protobuf/types/known/timestamppb"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestReplaceProduct(t *testing.T) {
	for i, suite := range testProductSuite {
		t.Run(fmt.Sprintf("변경 없이 요청 %d", i), func(t *testing.T) {
			res, err := facilities.Client().ReplaceProduct(context.Background(), suite)
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				validateProduct(t, suite, res)
			}
		})
	}

	for i, suite := range testProductSuite {
		switch i {
		case 0:
			suite.ProductName = beymonsGreen
		default:
			suite.ProductName = "이름 변경 테스트"
			suite.CreatedAt = timestamppb.Now()
		}
		t.Run(suite.ModelNumber, func(t *testing.T) {
			res, err := facilities.Client().ReplaceProduct(context.Background(), suite)
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				validateProduct(t, suite, res)
			}
		})
	}
}
