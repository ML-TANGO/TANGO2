package server

import (
	"math/rand"
	"testing"

	"context"
	"fmt"
	"time"

	"github.com/stretchr/testify/assert"
	"gitlab.suredatalab.kr/services/metadata"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/devices"
)

var (
	testTypeSuite    []*devices.SensorType
	testAgsMotorType = fmt.Sprintf("test_ags_%07d", rand.Int31n(9999999))
)

func TestCreateType(t *testing.T) {
	testCases := []struct {
		desc     string
		args     *devices.SensorType
		expected codes.Code
	}{
		{
			desc:     "필수 입력 항목 누락",
			args:     &devices.SensorType{},
			expected: codes.InvalidArgument,
		},
		{
			desc: "유효성 검사 오류 (type_id)",
			args: &devices.SensorType{
				TypeId: fmt.Sprintf("%d", time.Now().Unix()),
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "Attributes 누락",
			args: &devices.SensorType{
				TypeId:   fmt.Sprintf("test_%d", time.Now().Unix()),
				TypeName: "테스트 타입",
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "유효성 검사 오류 (attribute)",
			args: &devices.SensorType{
				TypeId:   fmt.Sprintf("test_%d", time.Now().Unix()),
				TypeName: "테스트 타입",
				Attributes: []*devices.SensorTypeAttribute{
					{
						Attribute: "1234",
						Type:      metadata.MetadataSchemaAttribute_bigint,
					},
				},
			},
			expected: codes.InvalidArgument,
		},
		{
			desc: "Success",
			args: &devices.SensorType{
				TypeId:   fmt.Sprintf("test_%d", time.Now().Unix()),
				TypeName: "테스트 타입",
				Attributes: []*devices.SensorTypeAttribute{
					{
						Attribute:   "temp",
						Unit:        "℃",
						Type:        metadata.MetadataSchemaAttribute_double_precision,
						Description: "온도",
					},
					{
						Attribute:   "humi",
						Unit:        "%",
						Type:        metadata.MetadataSchemaAttribute_smallint,
						Description: "습도",
					},
					{
						Attribute:   "image",
						Type:        metadata.MetadataSchemaAttribute_bytea,
						Description: "이미지",
					},
					{
						Attribute:   "event",
						Type:        metadata.MetadataSchemaAttribute_text,
						Length:      10,
						Description: "이벤트",
					},
				},
			},
			expected: codes.OK,
		},
		{
			desc: "Success",
			args: &devices.SensorType{
				TypeId:     fmt.Sprintf("test1_%d", time.Now().Unix()),
				MultiProbe: true,
				TypeName:   "테스트 타입",
				Attributes: []*devices.SensorTypeAttribute{
					{
						Attribute: "count",
						Type:      metadata.MetadataSchemaAttribute_bigint,
					},
				},
			},
			expected: codes.OK,
		},
		{
			desc: "Success",
			args: &devices.SensorType{
				TypeId:     fmt.Sprintf("test2_%d", time.Now().Unix()),
				MultiProbe: true,
				TypeName:   "테스트 타입",
				Attributes: []*devices.SensorTypeAttribute{
					{
						Attribute: "x",
						Type:      metadata.MetadataSchemaAttribute_real,
					},
					{
						Attribute: "y",
						Type:      metadata.MetadataSchemaAttribute_real,
					},
					{
						Attribute: "z",
						Type:      metadata.MetadataSchemaAttribute_real,
					},
				},
			},
			expected: codes.OK,
		},
		{
			desc: "agsmotor 타입 테스트",
			args: &devices.SensorType{
				TypeId:     testAgsMotorType,
				MultiProbe: true,
				TypeName:   "테스트 타입",
				Attributes: []*devices.SensorTypeAttribute{
					{
						Attribute: "mode",
						Type:      metadata.MetadataSchemaAttribute_text,
						Length:    20,
					},
					{
						Attribute: "mode_switch",
						Type:      metadata.MetadataSchemaAttribute_text,
						Length:    20,
					},
					{
						Attribute: "relay",
						Unit:      "%",
						Type:      metadata.MetadataSchemaAttribute_smallint,
					},
					{
						Attribute: "relay_switch",
						Unit:      "%",
						Type:      metadata.MetadataSchemaAttribute_smallint,
					},
					{
						Attribute: "open_rate",
						Unit:      "%",
						Type:      metadata.MetadataSchemaAttribute_smallint,
					},
				},
			},
			expected: codes.OK,
		},
	}

	ctx := context.Background()
	for _, suite := range testCases {
		t.Run(suite.desc, func(t *testing.T) {
			res, err := devices.Client().CreateType(ctx, suite.args)
			if suite.expected == codes.OK {
				if assert.NoError(t, err) && assert.NotNil(t, res, "Request: %+v", suite.args) {
					testTypeSuite = append(testTypeSuite, res)
					assert.Equal(t, suite.args.TypeId, res.TypeId)
					assert.Equal(t, suite.args.TypeName, res.TypeName)
					assert.Equal(t, suite.args.Description, res.Description)
					assert.Equal(t, suite.args.MultiProbe, res.MultiProbe)
					assert.NotEmpty(t, res.CreatedUserId)
					assert.NotEmpty(t, res.CreatedAt)
					if assert.Equal(t, len(suite.args.Attributes), len(res.Attributes)) {
						origin := make(map[string]*devices.SensorTypeAttribute)
						for _, attribute := range suite.args.Attributes {
							origin[attribute.Attribute] = attribute
						}

						for _, attribute := range res.Attributes {
							assert.Equal(t, suite.args.TypeId, attribute.TypeId)
							assert.NotEmpty(t, attribute.TypeName)
							originAttribute, ok := origin[attribute.Attribute]
							if assert.True(t, ok) {
								assert.Equal(t, originAttribute.Attribute, attribute.Attribute)
								assert.Equal(t, originAttribute.Unit, attribute.Unit)
								assert.Equal(t, originAttribute.Type, attribute.Type)
								assert.Equal(t, originAttribute.Length, attribute.Length)
								assert.Equal(t, originAttribute.Description, attribute.Description)
							}
						}
					}
				}
			} else if assert.Error(t, err, "Request: %+v", suite.args) {
				assert.Equal(t, suite.expected, status.Code(err), err.Error())
			}
		})
	}

	// 중복 생성
	for _, suite := range testTypeSuite {
		t.Run(suite.TypeId, func(t *testing.T) {
			res, err := devices.Client().CreateType(ctx, suite)
			assert.Nil(t, res)
			if assert.Error(t, err) {
				assert.Equal(t, status.Code(err), codes.AlreadyExists, err.Error())
			}
		})
	}
}
