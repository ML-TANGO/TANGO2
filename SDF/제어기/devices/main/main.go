// 서비스 메인
package main

import (
	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"google.golang.org/grpc"

	"gitlab.suredatalab.kr/beymons/devices"
	"gitlab.suredatalab.kr/beymons/devices/cmd"
	"gitlab.suredatalab.kr/beymons/devices/server"
)

func main() {
	s := &server.DevicesServer{}
	sdlmicro.Name(devices.PACKAGE_NAME)
	sdlmicro.Server(func(g *grpc.Server) {
		s.Init()
		devices.RegisterDeviceConfigsServer(g, s)
		devices.RegisterDevicesServer(g, s)
		devices.RegisterSensorTypesServer(g, s)
	})

	cmd.Execute()
}
