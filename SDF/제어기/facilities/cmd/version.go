package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

// versionCmd represents the version command
var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print the current release version",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("devel")
	},
}

func init() {
	rootCmd.AddCommand(versionCmd)
}
