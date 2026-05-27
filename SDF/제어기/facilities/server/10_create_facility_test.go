package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestCreateFacility(t *testing.T) {
	if len(testProductSuite) == 0 {
		t.FailNow()
	}

	testCases := []struct {
		desc     string
		args     *facilities.Facility
		expected codes.Code
	}{
		{
			desc:     "빈 요청",
			args:     &facilities.Facility{},
			expected: codes.InvalidArgument,
		},
		{
			desc: "존재하지 않는 사이트 ID",
			args: &facilities.Facility{
				SiteId:        "a.not-exist-123",
				GroupId:       "default",
				ManufactureId: testManufactureID,
				ModelNumber:   "test",
				FacilityName:  "테스트 설비",
				SerialNumber:  "test",
			},
			expected: codes.NotFound,
		},
		{
			desc: "존재하지 않는 그룹 ID",
			args: &facilities.Facility{
				SiteId:        testSiteID,
				GroupId:       "a.not-exist-123",
				ManufactureId: testManufactureID,
				ModelNumber:   "test",
				FacilityName:  "테스트 설비",
				SerialNumber:  "test",
			},
			expected: codes.NotFound,
		},
		{
			desc: "설비 정보 필수 필드 누락 (제조사ID)",
			args: &facilities.Facility{
				SiteId:       testSiteID,
				GroupId:      "default",
				ModelNumber:  testProductSuite[0].ModelNumber,
				SerialNumber: "test",
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "설비 정보 필수 필드 누락 (모델번호)",
			args: &facilities.Facility{
				SiteId:        testSiteID,
				GroupId:       "default",
				ManufactureId: testManufactureID,
				FacilityName:  "테스트 설비",
				SerialNumber:  "test",
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "잘못된 형식의 제품 정보",
			args: &facilities.Facility{
				SiteId:        testSiteID,
				GroupId:       "default",
				ManufactureId: testManufactureID,
				ModelNumber:   "test",
				FacilityName:  "테스트 설비",
				SerialNumber:  "test",
			},
			expected: codes.NotFound,
		},
		{
			desc: "성공 (필수 입력만)",
			args: &facilities.Facility{
				SiteId:        testSiteID,
				GroupId:       "default",
				ManufactureId: testManufactureID,
				ModelNumber:   testProductSuite[0].ModelNumber,
				FacilityName:  "테스트 설비",
				SerialNumber:  "test",
			},
			expected: codes.OK,
		},
		{
			desc: "존재하지 않는 사용자화 메타데이터",
			args: &facilities.Facility{
				SiteId:        testSiteID,
				GroupId:       "default",
				ManufactureId: testManufactureID,
				ModelNumber:   testProductSuite[0].ModelNumber,
				FacilityName:  "테스트 설비",
				SerialNumber:  "test",
				Attributes: map[string]string{
					"not_exist_1": "변경 테스트 1",
					"not_exist_2": "변경 테스트 2",
					"not_exist_3": "변경 테스트 3",
				},
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "성공",
			args: &facilities.Facility{
				SiteId:        testSiteID,
				GroupId:       "default",
				Latitude:      36.369,
				Longitude:     127.384,
				Altitude:      10,
				ManufactureId: testManufactureID,
				ModelNumber:   testProductSuite[0].ModelNumber,
				FacilityName:  "테스트 설비",
				SerialNumber:  "test",
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
			res, err := facilities.Client().CreateFacility(context.Background(), tc.args)
			if tc.expected == codes.OK {
				if assert.NoError(t, err) && assert.NotNil(t, res, "Request: %v", tc.args) {
					testFacilitySuite = append(testFacilitySuite, res)
				}
			} else if assert.Error(t, err, "Request: %+v", tc.args) {
				assert.Equal(t, tc.expected, status.Code(err), err.Error())
			}
		})
	}
}

func validFacility(t *testing.T, expected, actual *facilities.Facility) {
	assert.NotEmpty(t, actual.FacilityId, "FacilityId")
	assert.Equal(t, expected.FacilityName, actual.FacilityName, "FacilityName mismatch")
	assert.Equal(t, expected.SiteId, actual.SiteId, "SiteId mismatch")
	assert.Equal(t, expected.Latitude, actual.Latitude, "Latitude mismatch")
	assert.Equal(t, expected.Longitude, actual.Longitude, "Longitude mismatch")
	assert.Equal(t, expected.Altitude, actual.Altitude, "Altitude mismatch")
	assert.Equal(t, expected.ManufactureId, actual.ManufactureId, "ManufactureId mismatch")
	assert.Equal(t, expected.ModelNumber, actual.ModelNumber, "ModelNumber mismatch")
	assert.Equal(t, expected.SerialNumber, actual.SerialNumber, "SerialNumber mismatch")
	assert.Equal(t, len(expected.Attributes), len(actual.Attributes))
	assert.NotNil(t, actual.CreatedAt)
}
