package main

import (
	"context"
	"io"
	"log"
	"net/http"
	"os"
	"time"

	"gopkg.in/yaml.v3"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/client"
	"github.com/docker/go-connections/nat"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type OpRequest struct {
	Action     string   `json:"action"` // pull|create|start|stop|delete
	Image      string   `json:"image,omitempty"`
	Tag        string   `json:"tag,omitempty"`
	Name       string   `json:"name,omitempty"`
	Ports      []string `json:"ports,omitempty"`   // ["8080:80"]
	TimeoutSec int      `json:"timeout,omitempty"` // stop
	Force      bool     `json:"force,omitempty"`   // delete
	Volumes    bool     `json:"volumes,omitempty"` // delete: remove volumes
	Node       string   `json:"node,omitempty"`    // Node는 생략 가능: inventory에 노드가 1개면 자동 선택
}

type Inventory struct {
	Nodes map[string]NodeSpec `yaml:"nodes"`
}

type NodeSpec struct {
	Host       string `yaml:"host"`
	CA         string `yaml:"ca,omitempty"`
	Cert       string `yaml:"cert,omitempty"`
	Key        string `yaml:"key,omitempty"`
	TimeoutSec int    `yaml:"timeoutSec,omitempty"`
}

func main() {
	// 1) Load YAML inventory
	invPath := getenv("INVENTORY_FILE", "inventory.yaml")
	inv, err := loadInventory(invPath)
	if err != nil {
		log.Fatalf("load inventory: %v", err)
	}
	if len(inv.Nodes) == 0 {
		log.Fatal("no nodes found in inventory.yaml")
	}

	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery(), gin.Logger())

	r.GET("/healthz", func(c *gin.Context) { c.String(200, "ok") })
	r.GET("/metrics", gin.WrapH(promhttp.Handler()))
	

	// 2) 작업 엔드포인트
	r.POST("/ops", func(c *gin.Context) {
		var req OpRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": "invalid json"})
			return
		}

		ns, ok := selectNode(inv, req.Node)
		if !ok {
			c.JSON(400, gin.H{"error": "unknown node (specify a valid node or keep only one node in inventory)"})
			return
		}

		cli, err := newDockerClient(ns)
		if err != nil {
			c.JSON(500, gin.H{"error": "docker client: " + err.Error()})
			return
		}

		ctx, cancel := context.WithTimeout(c.Request.Context(), timeoutOf(ns))
		defer cancel()

		switch req.Action {
		case "pull":
			if req.Image == "" {
				c.JSON(400, gin.H{"error": "image required"})
				return
			}
			ref := req.Image
			if req.Tag != "" {
				ref = req.Image + ":" + req.Tag
			}
			rc, err := cli.ImagePull(ctx, ref, image.PullOptions{})
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			io.Copy(io.Discard, rc)
			rc.Close()
			c.Status(http.StatusNoContent)

		case "create":
			if req.Image == "" || req.Name == "" {
				c.JSON(400, gin.H{"error": "image and name required"})
				return
			}
			cfg, hostCfg, err := toConfigs(req.Image, req.Ports)
			if err != nil {
				c.JSON(400, gin.H{"error": err.Error()})
				return
			}
			resp, err := cli.ContainerCreate(ctx, cfg, hostCfg, nil, nil, req.Name)
			if err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.JSON(http.StatusCreated, gin.H{"container_id": resp.ID})

		case "start":
			if req.Name == "" {
				c.JSON(400, gin.H{"error": "name required"})
				return
			}
			if err := cli.ContainerStart(ctx, req.Name, container.StartOptions{}); err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.Status(http.StatusNoContent)

		case "stop":
			if req.Name == "" {
				c.JSON(400, gin.H{"error": "name required"})
				return
			}
			var to *int
			if req.TimeoutSec > 0 {
				to = &req.TimeoutSec
			}
			if err := cli.ContainerStop(ctx, req.Name, container.StopOptions{Timeout: to}); err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.Status(http.StatusNoContent)

		case "delete":
			if req.Name == "" {
				c.JSON(400, gin.H{"error": "name required"})
				return
			}
			if err := cli.ContainerRemove(ctx, req.Name, container.RemoveOptions{
				Force: req.Force, RemoveVolumes: req.Volumes,
			}); err != nil {
				c.JSON(500, gin.H{"error": err.Error()})
				return
			}
			c.Status(http.StatusNoContent)

		default:
			c.JSON(400, gin.H{"error": "unknown action"})
		}
	})

	listen := getenv("CP_LISTEN", ":8080")
	log.Printf("[controlplane] listening on %s (inventory=%s, nodes=%d)", listen, invPath, len(inv.Nodes))
	log.Fatal(r.Run(listen))
}

// ───────────── helpers ─────────────

func loadInventory(path string) (*Inventory, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var inv Inventory
	if err := yaml.Unmarshal(b, &inv); err != nil {
		return nil, err
	}
	return &inv, nil
}

func selectNode(inv *Inventory, name string) (NodeSpec, bool) {
	// node 미지정 & inventory에 노드가 1개면 자동 선택
	if name == "" && len(inv.Nodes) == 1 {
		for _, v := range inv.Nodes {
			return v, true
		}
	}
	ns, ok := inv.Nodes[name]
	return ns, ok
}

func newDockerClient(ns NodeSpec) (*client.Client, error) {
	opts := []client.Opt{
		client.WithHost(ns.Host),
		client.WithAPIVersionNegotiation(),
	}
	if ns.CA != "" && ns.Cert != "" && ns.Key != "" {
		opts = append(opts, client.WithTLSClientConfig(ns.CA, ns.Cert, ns.Key))
	}
	return client.NewClientWithOpts(opts...)
}

func timeoutOf(ns NodeSpec) time.Duration {
	if ns.TimeoutSec <= 0 {
		return 30 * time.Second
	}
	return time.Duration(ns.TimeoutSec) * time.Second
}

func toConfigs(image string, specs []string) (*container.Config, *container.HostConfig, error) {
	exposed := nat.PortSet{}
	bindings := nat.PortMap{}
	for _, s := range specs {
		pm, err := nat.ParsePortSpec(s)
		if err != nil {
			return nil, nil, err
		}
		for _, m := range pm {
			exposed[m.Port] = struct{}{}
			bindings[m.Port] = append(bindings[m.Port], nat.PortBinding{
				HostIP: m.Binding.HostIP, HostPort: m.Binding.HostPort,
			})
		}
	}
	return &container.Config{Image: image, ExposedPorts: exposed},
		&container.HostConfig{PortBindings: bindings}, nil
}

func getenv(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
