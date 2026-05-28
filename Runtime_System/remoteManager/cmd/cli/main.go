package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"

	"github.com/spf13/cobra"
)

var cp string // ControlPlane URL

type OpRequest struct {
	Action     string   `json:"action"` // pull|create|start|stop|delete
	Image      string   `json:"image,omitempty"`
	Tag        string   `json:"tag,omitempty"`
	Name       string   `json:"name,omitempty"`
	Ports      []string `json:"ports,omitempty"` // e.g. ["8080:80"]
	TimeoutSec int      `json:"timeout,omitempty"`
	Force      bool     `json:"force,omitempty"`
	Volumes    bool     `json:"volumes,omitempty"`
	Node       string   `json:"node,omitempty"` // target node name
}

func main() {
	root := &cobra.Command{
		Use: "sdxr",
		PersistentPreRun: func(cmd *cobra.Command, args []string) {
			if cp == "" {
				cp = os.Getenv("CP_ADDR")
			}
			if cp == "" {
				cp = "http://localhost:8080"
			}
			cp = strings.TrimRight(cp, "/")
		},
	}
	root.PersistentFlags().StringVar(&cp, "cp", "", "ControlPlane URL (default $CP_ADDR or http://localhost:8080)")

	root.AddCommand(
		cmdPull(), cmdCreate(), cmdStart(), cmdStop(), cmdDelete(),
	)
	if err := root.Execute(); err != nil {
		os.Exit(1)
	}
}

func postOp(r OpRequest) error {
	body, _ := json.Marshal(r)
	resp, err := http.Post(cp+"/ops", "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	_, _ = io.Copy(os.Stdout, resp.Body)
	fmt.Println()
	return nil
}

func cmdPull() *cobra.Command {
	var image, tag string
	var nodes []string
	c := &cobra.Command{
		Use:   "pull",
		Short: "Pull image on the remote nodes (configured in inventory.yaml)",
		RunE: func(cmd *cobra.Command, args []string) error {
			if image == "" {
				return fmt.Errorf("--image required")
			}
			if len(nodes) == 0 {
				nodes = []string{""} // inventory가 1개일 경우 기본값
			}
			for _, n := range nodes {
				fmt.Printf("==> pulling %s:%s on %s\n", image, tag, n)
				err := postOp(OpRequest{
					Action: "pull",
					Image:  image,
					Tag:    tag,
					Node:   n,
				})
				if err != nil {
					fmt.Printf("  [error] %v\n", err)
				}
			}
			return nil
		},
	}
	c.Flags().StringVar(&image, "image", "", "image name (e.g. nginx)")
	c.Flags().StringVar(&tag, "tag", "latest", "image tag")
	c.Flags().StringSliceVar(&nodes, "nodes", nil, "target nodes (comma-separated)")
	return c
}

func cmdCreate() *cobra.Command {
	var image, tag, name string
	var nodes []string
	var ports []string
	c := &cobra.Command{
		Use:   "create",
		Short: "Create container on remote nodes (configured in inventory.yaml)",
		RunE: func(cmd *cobra.Command, args []string) error {
			if image == "" || name == "" {
				return fmt.Errorf("--image and --name required")
			}
			if len(nodes) == 0 {
				nodes = []string{""}
			}
			for _, n := range nodes {
				fmt.Printf("==> creating container '%s' (%s:%s) on %s\n", name, image, tag, n)
				err := postOp(OpRequest{
					Action: "create",
					Image:  image,
					Tag:    tag,
					Name:   name,
					Ports:  ports,
					Node:   n,
				})
				if err != nil {
					fmt.Printf("  [error] %v\n", err)
				}
			}
			return nil
		},
	}
	c.Flags().StringVar(&image, "image", "", "image (e.g. nginx)")
	c.Flags().StringVar(&tag, "tag", "latest", "image tag (default: latest)")
	c.Flags().StringVar(&name, "name", "", "container name")
	c.Flags().StringSliceVarP(&ports, "publish", "p", nil, "publish ports (e.g. 8080:80)")
	c.Flags().StringSliceVar(&nodes, "nodes", nil, "target nodes (comma-separated)")
	return c
}

func cmdStart() *cobra.Command {
	var name string
	var nodes []string
	c := &cobra.Command{
		Use:   "start",
		Short: "Start container on remote nodes (configured in inventory.yaml)",
		RunE: func(cmd *cobra.Command, args []string) error {
			if name == "" {
				return fmt.Errorf("--name required")
			}
			if len(nodes) == 0 {
				nodes = []string{""}
			}
			for _, n := range nodes {
				fmt.Printf("==> starting container '%s' on %s\n", name, n)
				err := postOp(OpRequest{
					Action: "start",
					Name:   name,
					Node:   n,
				})
				if err != nil {
					fmt.Printf("  [error] %v\n", err)
				}
			}
			return nil
		},
	}
	c.Flags().StringVar(&name, "name", "", "container name")
	c.Flags().StringSliceVar(&nodes, "nodes", nil, "target nodes (comma-separated)")
	return c
}

func cmdStop() *cobra.Command {
	var name string
	var timeout int
	var nodes []string
	c := &cobra.Command{
		Use:   "stop",
		Short: "Stop container on the remote nodes (configured in inventory.yaml)",
		RunE: func(cmd *cobra.Command, args []string) error {
			if name == "" {
				return fmt.Errorf("--name required")
			}
			if len(nodes) == 0 {
				nodes = []string{""}
			}
			for _, n := range nodes {
				fmt.Printf("==> stopping container '%s' on %s\n", name, n)
				err := postOp(OpRequest{
					Action:     "stop",
					Name:       name,
					TimeoutSec: timeout,
					Node:       n,
				})
				if err != nil {
					fmt.Printf("  [error] %v\n", err)
				}
			}
			return nil
		},
	}
	c.Flags().StringVar(&name, "name", "", "container name")
	c.Flags().IntVar(&timeout, "timeout", 10, "graceful stop timeout seconds")
	c.Flags().StringSliceVar(&nodes, "nodes", nil, "target nodes (defined in inventory)")
	return c
}

func cmdDelete() *cobra.Command {
	var name string
	var nodes []string
	var force, volumes bool
	c := &cobra.Command{
		Use:   "delete",
		Short: "Delete container on the remote nodes (configured in inventory.yaml)",
		RunE: func(cmd *cobra.Command, args []string) error {
			if name == "" {
				return fmt.Errorf("--name required")
			}
			if len(nodes) == 0 {
				nodes = []string{""}
			}
			for _, n := range nodes {
				fmt.Printf("==> deleting container '%s' on %s\n", name, n)
				err := postOp(OpRequest{
					Action:  "delete",
					Name:    name,
					Force:   force,
					Volumes: volumes,
					Node:    n,
				})
				if err != nil {
					fmt.Printf("  [error] %v\n", err)
				}
			}
			return nil
		},
	}
	c.Flags().StringVar(&name, "name", "", "container name")
	c.Flags().BoolVar(&force, "force", false, "force remove")
	c.Flags().BoolVar(&volumes, "volumes", false, "remove volumes")
	c.Flags().StringSliceVar(&nodes, "nodes", nil, "target nodes (defined in inventory)")
	return c
}
