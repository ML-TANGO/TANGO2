package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	collects "gitlab.suredatalab.kr/beymons/collects"
)

func TestStatistics(t *testing.T) {
	res, err := collects.Client().Statistics(context.Background(), &collects.StatisticsRequest{})
	assert.NoError(t, err)
	assert.NotNil(t, res)
}
