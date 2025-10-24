package server

import (
	"testing"

	"context"
	"fmt"
	"os"
	"time"

	"gitlab.suredatalab.kr/beymons/collects"
	"gitlab.suredatalab.kr/beymons/devices"
	devSrv "gitlab.suredatalab.kr/beymons/devices/server"
	"gitlab.suredatalab.kr/beymons/sites"
	siteSrv "gitlab.suredatalab.kr/beymons/sites/server"
	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/services/metadata"
	metaSrv "gitlab.suredatalab.kr/services/metadata/server"
)

var (
	testSensorType string
	testGwID       string
	testNodeID     string
	closeConsumer  = make(chan bool, 1)
)

func TestMain(m *testing.M) {
	os.Setenv("SECURE_MODE", "disable")

	ensureTestSuite()
	code := m.Run()
	clearTestSuite()
	os.Exit(code)
}

func ensureTestSuite() {
	// 메타데이터 서비스 실행
	metadata.TestClient(metaSrv.TestServer())
	// 장치 관리 서비스 실행
	devices.TestClient(devSrv.TestServer())
	// 사이트 관리 서비스 실행
	sites.TestClient(siteSrv.TestServer())

	// 이전 스트림 제거
	async.DeleteStream(collects.PACKAGE_NAME)

	// 센서 타입 생성
	sensorType, err := devices.Client().CreateType(context.Background(), &devices.SensorType{
		TypeId:     fmt.Sprintf("test_m%d", time.Now().Unix()),
		MultiProbe: true,
		TypeName:   "테스트 타입",
		Attributes: []*devices.SensorTypeAttribute{
			{
				Attribute: "temp",
				Type:      metadata.MetadataSchemaAttribute_real,
			},
		},
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
	}
	testSensorType = sensorType.TypeId

	currentTime := time.Now()

	// GW 생성
	gw, err := devices.Client().CreateDevice(context.Background(), &devices.Device{
		DeviceId:    fmt.Sprintf("TGW%d", currentTime.Unix()),
		DisplayName: "TEST GW",
		DeviceRole:  devices.DeviceRole_GATEWAY,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
	} else {
		testGwID = gw.DeviceId
	}

	// 노드 생성
	node, err := devices.Client().CreateDevice(context.Background(), &devices.Device{
		DeviceId:    fmt.Sprintf("TN%d", currentTime.Unix()),
		DisplayName: "TEST NODE",
		DeviceRole:  devices.DeviceRole_NODE,
		Sensors: []*devices.Sensor{
			{
				ChannelId:  1,
				SensorType: testSensorType,
			},
			{
				ChannelId:  2,
				SensorType: testSensorType,
			},
		},
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
	} else {
		testNodeID = node.DeviceId
	}

	// 기본 사이트로 출고
	fmt.Fprintln(os.Stdout, "outbound to sdl")
	if _, err := sites.Client().Outbound(context.Background(), &sites.OutboundRequest{
		SiteId: "sdl",
		Devices: []*sites.SiteDevice{
			{
				DeviceId:  testGwID,
				Latitude:  36.395820,
				Longitude: 127.407210,
			},
			{
				DeviceId:  testNodeID,
				Latitude:  36.395821,
				Longitude: 127.407211,
			},
		},
	}); err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
	}

	// 서비스 초기화
	collects.TestClient(TestServer())
	go CollectConsumer(closeConsumer)
}

func clearTestSuite() {
	closeConsumer <- true

	for _, devID := range []string{
		testNodeID,
		testGwID,
	} {
		if _, err := sites.Client().DeleteDevice(context.Background(), &sites.DeleteDeviceRequest{
			SiteId:   "sdl",
			DeviceId: devID,
		}); err != nil {
			fmt.Fprintln(os.Stderr, err.Error())
		}

		if _, err := devices.Client().DeleteDevice(context.Background(), &devices.DeviceRequest{
			DeviceId: devID,
		}); err != nil {
			fmt.Fprintln(os.Stderr, err.Error())
		}
	}

	if _, err := devices.Client().DeleteType(context.Background(), &devices.SensorTypeRequest{
		TypeId: testSensorType,
	}); err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
	}
}
