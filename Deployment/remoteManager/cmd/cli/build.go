package main

// build.go: 이미지 빌드 명령 (DEV_PLAN 4.4)
//   sdxr build --src app.tar.gz --config build.yaml   업로드 후 작업 ID 출력
//   sdxr build status <id>                             상태 조회
//   sdxr build logs <id> [--follow]                    로그 조회
//   sdxr build list                                    작업 목록
// BUILD_TOKEN 환경변수가 설정되어 있으면 Bearer 토큰으로 전송한다.

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/spf13/cobra"
)

func cmdBuild() *cobra.Command {
	var src, cfgPath string
	c := &cobra.Command{
		Use:   "build",
		Short: "Upload source and build.yaml to ImageMaker and start an image build",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			if src == "" || cfgPath == "" {
				return fmt.Errorf("--src and --config required")
			}
			return submitBuild(src, cfgPath)
		},
	}
	c.Flags().StringVar(&src, "src", "", "source archive (tar.gz)")
	c.Flags().StringVar(&cfgPath, "config", "", "build.yaml path")
	c.AddCommand(cmdBuildStatus(), cmdBuildLogs(), cmdBuildList())
	return c
}

func submitBuild(src, cfgPath string) error {
	var body bytes.Buffer
	mw := multipart.NewWriter(&body)
	if err := addFormFile(mw, "source", src); err != nil {
		return err
	}
	if err := addFormFile(mw, "config", cfgPath); err != nil {
		return err
	}
	if err := mw.Close(); err != nil {
		return err
	}

	resp, err := buildRequest(http.MethodPost, "/builds", &body, mw.FormDataContentType())
	if err != nil {
		return err
	}
	return printResponse(resp)
}

func cmdBuildStatus() *cobra.Command {
	return &cobra.Command{
		Use:   "status <id>",
		Short: "Show build job status",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			resp, err := buildRequest(http.MethodGet, "/builds/"+args[0], nil, "")
			if err != nil {
				return err
			}
			return printResponse(resp)
		},
	}
}

func cmdBuildList() *cobra.Command {
	return &cobra.Command{
		Use:   "list",
		Short: "List build jobs",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			resp, err := buildRequest(http.MethodGet, "/builds", nil, "")
			if err != nil {
				return err
			}
			return printResponse(resp)
		},
	}
}

func cmdBuildLogs() *cobra.Command {
	var follow bool
	c := &cobra.Command{
		Use:   "logs <id>",
		Short: "Show build logs (use --follow to wait until the job finishes)",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			id := args[0]
			printed := 0
			for {
				resp, err := buildRequest(http.MethodGet, "/builds/"+id+"/logs", nil, "")
				if err != nil {
					return err
				}
				data, err := io.ReadAll(resp.Body)
				resp.Body.Close()
				if err != nil {
					return err
				}
				if resp.StatusCode >= 300 {
					return fmt.Errorf("logs: %s", string(data))
				}
				if printed < len(data) {
					os.Stdout.Write(data[printed:])
					printed = len(data)
				}
				if !follow || jobFinished(id) {
					return nil
				}
				time.Sleep(2 * time.Second)
			}
		},
	}
	c.Flags().BoolVarP(&follow, "follow", "f", false, "keep polling until the job finishes")
	return c
}

// jobFinished: 작업이 종료 상태(succeeded/failed)인지 확인
func jobFinished(id string) bool {
	resp, err := buildRequest(http.MethodGet, "/builds/"+id, nil, "")
	if err != nil {
		return true // 조회 실패 시 더 기다리지 않는다
	}
	defer resp.Body.Close()
	var v struct {
		Status string `json:"status"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&v); err != nil {
		return true
	}
	return v.Status == "succeeded" || v.Status == "failed"
}

func addFormFile(mw *multipart.Writer, field, path string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	part, err := mw.CreateFormFile(field, filepath.Base(path))
	if err != nil {
		return err
	}
	_, err = io.Copy(part, f)
	return err
}

func buildRequest(method, path string, body io.Reader, contentType string) (*http.Response, error) {
	req, err := http.NewRequest(method, cp+path, body)
	if err != nil {
		return nil, err
	}
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	if tok := os.Getenv("BUILD_TOKEN"); tok != "" {
		req.Header.Set("Authorization", "Bearer "+tok)
	}
	return http.DefaultClient.Do(req)
}

func printResponse(resp *http.Response) error {
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	fmt.Println(string(data))
	if resp.StatusCode >= 300 {
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	return nil
}
