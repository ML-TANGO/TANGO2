package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"gitlab.suredatalab.kr/beymons/collects/server"
)

var cleanCmd = &cobra.Command{
	Use:   "clean",
	Short: "Remove related DB",
	Run: func(cmd *cobra.Command, args []string) {
		s := server.CollectsServer{}
		if err := s.Prune(); err != nil {
			fmt.Fprintln(os.Stderr, err.Error())
		}
	},
}

func init() {
	rootCmd.AddCommand(cleanCmd)
}
