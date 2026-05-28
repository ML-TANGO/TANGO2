// 서비스 제어 명령
//
// 서비스를 제어하기 위한 CLI(Command Line Interface)로 다음의 명령을 지원한다:
//   - up: 서비스 실행
//   - init: 서비스 초기화 명령
//   - clear: 데이터 정리 명령
package cmd

import (
	"os"

	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
)

var rootCmd = sdlmicro.BaseCommand("facilities", "A gRPC based service")

// Execute 함수는 CLI 명령을 연결한다.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(-1)
	}
}
