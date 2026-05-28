package server

import (
	"testing"

	"context"
	"fmt"
	"os"
	"time"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/services/metadata"
	mdSrv "gitlab.suredatalab.kr/services/metadata/server"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/structpb"

	"gitlab.suredatalab.kr/beymons/devices"
	devSrv "gitlab.suredatalab.kr/beymons/devices/server"
	"gitlab.suredatalab.kr/beymons/facilities"
	"gitlab.suredatalab.kr/beymons/sites"
	siteSrv "gitlab.suredatalab.kr/beymons/sites/server"
)

var (
	testTime      = time.Now()
	closeConsumer = make(chan bool, 1)
	sa            context.Context
	testClaims    *auth.Claims

	// 테스트 제품 리스트
	testProductSuite []*facilities.Product
	// 테스트 설비 리스트
	testFacilitySuite []*facilities.Facility
	// 테스트에 사용된 장치들
	testDevices []*devices.Device
	// 테스트 사이트
	testSiteID = fmt.Sprintf("test_customer_%d", testTime.UnixMilli())
	// 테스트 제조사
	testManufactureID = fmt.Sprintf("test_manufacture_%d", testTime.UnixMilli())
	// 테스트 GW
	testGateway = fmt.Sprintf("TG%d", testTime.Unix())
	// 테스트 센서 타입
	testSensorType string
	// 테스트에 사용되는 사용자화 메타데이터 항목
	testAttributes = []string{
		fmt.Sprintf("test1%d", testTime.Unix()),
		fmt.Sprintf("test2%d", testTime.Unix()),
		fmt.Sprintf("test3%d", testTime.Unix()),
	}
)

// 테스트가 필요한 제품으로 제품명으로 설정함
var (
	beymonsGreen      = "GREEN"
	beymonsGreenCount = 10
)

func TestMain(m *testing.M) {
	// 서비스 계정 인증
	ctx, err := auth.ServiceAccount()
	if err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		os.Exit(1)
	}
	sa = ctx
	testClaims, _ = auth.GetClaim(ctx)
	os.Setenv("SECURE_MODE", "disable")

	ensureTestCases()
	code := m.Run()
	clearTestSuite()
	os.Exit(code)
}

func ensureTestCases() {
	// 메타데이터 관리 서비스 시작
	metadata.TestClient(mdSrv.TestServer())
	// 장치 관리 서비스 시작
	devices.TestClient(devSrv.TestServer())
	go devSrv.DeviceConsumer(closeConsumer)
	// 사이트 관리 서비스 시작
	sites.TestClient(siteSrv.TestServer())
	// 서비스 초기화
	facilities.TestClient(TestServer())

	// 대상 사이트 생성
	if _, err := sites.Client().Create(context.Background(), &sites.Site{
		SiteId:   testSiteID,
		SiteName: "테스트 농장",
	}); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create site: %s\n", err.Error())
	}

	// 사이트 사용자 추가
	if _, err := sites.Client().AddUser(context.Background(), &sites.AddUserRequest{
		SiteId: testSiteID,
		User:   testClaims.Username,
		Role:   sites.SiteUser_manager,
	}); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to add user: %s\n", err.Error())
	}

	// 테스트에 필요한 데이터 추가
	createTestSensorType()
	createTestGateway()
	createTestDoc(PRODUCT_NAME)
	createTestDoc(facilities.PACKAGE_NAME)
}

func clearTestSuite() {
	closeConsumer <- true

	// 설비 및 제품 제거
	for _, facility := range testFacilitySuite {
		if _, err := facilities.Client().DeleteFacility(context.Background(), &facilities.FacilityRequest{
			FacilityId: facility.FacilityId,
		}); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to delete facility %s: %s\n", facility.FacilityId, err.Error())
		}
	}
	for _, product := range testProductSuite {
		if _, err := facilities.Client().DeleteProduct(context.Background(), &facilities.ProductRequest{
			ManufactureId: product.ManufactureId,
			ModelNumber:   product.ModelNumber,
		}); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to delete product %s %s: %s", product.ManufactureId, product.ModelNumber, err.Error())
		}
	}

	// 사이트 제거
	for _, siteID := range []string{testManufactureID, testSiteID} {
		if _, err := sites.Client().Delete(context.Background(), &sites.SiteRequest{SiteId: siteID}); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to delete site %s: %s\n", siteID, err.Error())
		}
	}

	// 장치 제거
	for _, device := range testDevices {
		if _, err := devices.Client().DeleteDevice(context.Background(), &devices.DeviceRequest{DeviceId: device.DeviceId}); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to delete device %s: %s\n", device.DeviceId, err.Error())
		}
	}
}

// 사용자화 메타데이터 항목 추가
func createTestDoc(kind string) {
	for _, key := range testAttributes {
		if _, err := metadata.Client().InsertMetadata(context.Background(), &metadata.InsertMetadataRequest{
			MetadataId: "documentations",
			Contents: &structpb.Struct{
				Fields: map[string]*structpb.Value{
					"kind":  structpb.NewStringValue(kind),
					"name":  structpb.NewStringValue(key),
					"ratio": structpb.NewNumberValue(1),
				},
			},
		}); err != nil && status.Code(err) != codes.AlreadyExists {
			fmt.Fprintf(os.Stderr, "Failed to create documentations %s: %s\n", key, err.Error())
		}
	}
}

// 게이트웨이 생성 및 사이트 출고
func createTestGateway() {
	// 테스트용 게이트웨이 생성
	if res, err := devices.Client().CreateDevice(context.Background(), &devices.Device{
		DeviceId:   testGateway,
		DeviceRole: devices.DeviceRole_GATEWAY,
	}); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create gateway: %s\n", err.Error())
		os.Exit(1)
	} else {
		testDevices = append(testDevices, res)
	}

	if _, err := sites.Client().Outbound(context.Background(), &sites.OutboundRequest{
		SiteId: testSiteID,
		Devices: []*sites.SiteDevice{
			{
				DeviceId:    testGateway,
				DisplayName: "테스트 게이트웨이",
			},
		},
	}); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to outbound to site: %s\n", err.Error())
		os.Exit(1)
	}
}

// 테스트용 센서 타입 생성
func createTestSensorType() {
	// agsmotor_green 타입 생성 (실제 타입에 대한 테스트이므로 삭제하면 안됨)
	if _, err := devices.Client().CreateType(context.Background(), &devices.SensorType{
		TypeId:      "agsmotor_green",
		MultiProbe:  true,
		Description: "테스트 단계에서 생성됨",
		Attributes: []*devices.SensorTypeAttribute{
			{
				Attribute: "mode",
				Type:      metadata.MetadataSchemaAttribute_text,
				Length:    10,
			},
			{
				Attribute: "mode_switch",
				Type:      metadata.MetadataSchemaAttribute_text,
				Length:    5,
			},
			{
				Attribute: "relay",
				Type:      metadata.MetadataSchemaAttribute_smallint,
			},
			{
				Attribute: "relay_switch",
				Type:      metadata.MetadataSchemaAttribute_smallint,
			},
			{
				Attribute: "open_rate",
				Type:      metadata.MetadataSchemaAttribute_smallint,
			},
		},
	}); err != nil {
		if status.Code(err) != codes.AlreadyExists {
			fmt.Fprintf(os.Stderr, "Failed to create sensor type: %s\n", err.Error())
			os.Exit(1)
		}
	}

	// 테스트용 센서
	testSensorType = fmt.Sprintf("test_%d", time.Now().Unix())
	if _, err := devices.Client().CreateType(context.Background(), &devices.SensorType{
		TypeId:     testSensorType,
		MultiProbe: true,
		TypeName:   "테스트 타입",
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
		},
	}); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create sensor type: %s\n", err.Error())
		os.Exit(1)
	}
}

// 노드 생성 및 사이트 출고
func createTestNode(kind string) (*devices.Device, error) {
	if len(kind) == 0 {
		kind = "N"
	}
	req := &devices.Device{
		DeviceId:   fmt.Sprintf("TN%s%d", string(kind[0]), time.Now().Unix()),
		DeviceRole: devices.DeviceRole_NODE,
		Sensors: []*devices.Sensor{
			{
				ChannelId:  1,
				SensorType: testSensorType,
				Probes:     1,
			},
			{
				ChannelId:  2,
				SensorType: "agsmotor_green",
				Probes:     16,
			},
		},
	}
	switch kind {
	case beymonsGreen:
		req.Sensors = nil
		for i := 0; i < beymonsGreenCount; i++ {
			req.Sensors = append(req.Sensors, &devices.Sensor{
				ChannelId:  uint32(i) + 1,
				SensorType: "agsmotor_green",
				Probes:     16,
			})
		}
	}

	// 테스트용 장치 생성
	if res, err := devices.Client().CreateDevice(context.Background(), req); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create node: %s\n", err.Error())
		return nil, err
	} else {
		testDevices = append(testDevices, res)
		req = res
	}

	// 사이트로 출고
	if _, err := sites.Client().Outbound(context.Background(), &sites.OutboundRequest{
		SiteId: testSiteID,
		Devices: []*sites.SiteDevice{
			{
				DeviceId:    req.DeviceId,
				DisplayName: "테스트 노드",
			},
		},
	}); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to outbound to site: %s\n", err.Error())
		return nil, err
	}

	return req, nil
}
