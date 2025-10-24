package cmd

import (
	"bufio"
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/encoding/protojson"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/collects"
)

// viewCmd represents the view command
var viewCmd = &cobra.Command{
	Use:   "view [received_at] ",
	Short: "View received data",
	Run: func(cmd *cobra.Command, args []string) {
		db, err := pgorm.ConnectDB()
		if err != nil {
			fmt.Fprintln(os.Stderr, err.Error())
			os.Exit(-1)
		}

		// DB Connection
		conn := db.Conn()
		defer conn.Close()

		query := conn.Model((*collects.ReceiveHistory)(nil))
		query.Order("received_at DESC")
		if len(args) > 0 {
			query.Where("received_at = ?", args[0])
		} else {
			query.Where("error IS NOT NULL")
		}

		reader := bufio.NewReader(os.Stdin)
		if err := query.ForEach(func(tuple *collects.ReceiveHistory) error {
			payload := &collects.ReceiveData{}
			if err := proto.Unmarshal(tuple.Origin, payload); err != nil {
				fmt.Fprintln(os.Stderr, err.Error())
				os.Exit(-1)
			}

			data, err := protojson.MarshalOptions{
				Multiline: true,
				Indent:    "  ",
			}.Marshal(payload.Data)
			if err != nil {
				fmt.Fprintln(os.Stderr, err.Error())
				os.Exit(-1)
			}

			fmt.Printf("Topic: %s/_data/%s received at %q\n", payload.SiteId, payload.GatewayId, payload.ReceivedAt.AsTime())
			fmt.Println("Error:", tuple.Error)
			fmt.Println(string(data))
			for true {
				fmt.Print("more... (<ENTER> to continue, 'ctrl+c' to cancel)")
				if _, _, err := reader.ReadRune(); err != nil {
					fmt.Fprintln(os.Stderr, err.Error())
					os.Exit(-1)
				}

				return nil
			}

			return nil
		}); err != nil {
			fmt.Fprintln(os.Stderr, err.Error())
			os.Exit(-1)
		}
	},
}

func init() {
	rootCmd.AddCommand(viewCmd)
}
