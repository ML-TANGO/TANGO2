package cmd

import (
	"os"
	"os/signal"
	"syscall"

	"github.com/spf13/cobra"
	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"

	"gitlab.suredatalab.kr/beymons/collects/server"
)

var upCmd = &cobra.Command{
	Use:   "up",
	Short: "up runs both RPC service",
	Run: func(cmd *cobra.Command, args []string) {
		c := make(chan os.Signal, 1)
		signal.Notify(c, os.Interrupt, syscall.SIGTERM)

		close := make(chan bool, 1)
		go server.CollectConsumer(close)

		go func() {
			if err := sdlmicro.Run(); err != nil {
				panic(err.Error())
			}
		}()

		<-c
		close <- true
		sdlmicro.Shutdown()
	},
}

func init() {
	rootCmd.AddCommand(upCmd)
}
