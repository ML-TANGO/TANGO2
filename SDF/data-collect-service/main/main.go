// 서비스 메인
package main

import (
	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"google.golang.org/grpc"

	"gitlab.suredatalab.kr/beymons/collects"
	"gitlab.suredatalab.kr/beymons/collects/cmd"
	"gitlab.suredatalab.kr/beymons/collects/server"
)

func main() {
	s := &server.CollectsServer{}
	sdlmicro.Name(collects.PACKAGE_NAME)
	sdlmicro.Server(func(g *grpc.Server) {
		s.Init()
		collects.RegisterCollectsServer(g, s)
	})

	cmd.Execute()
}
