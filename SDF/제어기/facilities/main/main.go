// 서비스 메인
package main

import (
	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"google.golang.org/grpc"

	"gitlab.suredatalab.kr/beymons/facilities"
	"gitlab.suredatalab.kr/beymons/facilities/cmd"
	"gitlab.suredatalab.kr/beymons/facilities/server"
)

func main() {
	s := &server.FacilitiesServer{}
	sdlmicro.Name(facilities.PACKAGE_NAME)
	sdlmicro.Server(func(g *grpc.Server) {
		s.Init()
		facilities.RegisterFacilitiesServer(g, s)
		facilities.RegisterProductsServer(g, s)
	})

	cmd.Execute()
}
