package cmd

import (
	"github.com/spf13/cobra"

	"gitlab.suredatalab.kr/beymons/collects/server"
)

// checkCmd represents the check command
var checkCmd = &cobra.Command{
	Use:   "check",
	Short: "Check disconnected devices",
	Run: func(cmd *cobra.Command, args []string) {
		server.CheckDisconnected()
	},
}

func init() {
	rootCmd.AddCommand(checkCmd)
}
