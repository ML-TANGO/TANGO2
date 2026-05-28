package cmd

import (
	"os"

	"github.com/spf13/cobra"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/devices"
)

// checkCmd represents the check command
var checkCmd = &cobra.Command{
	Use:   "check",
	Short: "Check timeout command",
	Run: func(cmd *cobra.Command, args []string) {
		interval := os.Getenv("REQUEST_TIMEOUT")
		if len(interval) == 0 {
			interval = "5m"
		}

		// DB Connection
		conn := pgorm.Conn()
		defer conn.Close()

		query := conn.Model((*devices.DeviceCommandHistory)(nil))
		query.Where("created_at <= NOW() - INTERVAL ?", interval)
		query.Where("status = ?", devices.DeviceCommandHistory_PROCESSING)
		query.Set("status = ?", devices.DeviceCommandHistory_TIMEOUT)

		res, err := query.Update()
		if err != nil {
			log.Errorf("Failed to check timeout: %s", err.Error())
		} else {
			log.Infof("%d request is timeout", res.RowsAffected())
		}

	},
}

func init() {
	rootCmd.AddCommand(checkCmd)

	// Here you will define your flags and configuration settings.

	// Cobra supports Persistent Flags which will work for this command
	// and all subcommands, e.g.:
	// checkCmd.PersistentFlags().String("foo", "", "A help for foo")

	// Cobra supports local flags which will only run when this command
	// is called directly, e.g.:
	// checkCmd.Flags().BoolP("toggle", "t", false, "Help message for toggle")
}
