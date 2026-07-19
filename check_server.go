/// -*- coding: utf-8 -*-
/// ============================================================
/// 拉格朗日AI — Go 语言工具
/// 功能：端口检查、服务状态监控、简单HTTP请求
/// 编译：go build -o lagrange_check.exe check_server.go
/// ============================================================

package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

const defaultBaseURL = "http://127.0.0.1:3000"

// HealthResponse 健康检查响应
type HealthResponse struct {
	Status    string `json:"status"`
	Timestamp string `json:"timestamp"`
	IndexBuilt bool  `json:"index_built"`
}

// ShipsResponse 舰船数据响应
type ShipsResponse struct {
	Ships  []map[string]interface{} `json:"ships"`
	Count  int                      `json:"count"`
	Source string                   `json:"source"`
}

func checkHealth(baseURL string) (*HealthResponse, error) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/health")
	if err != nil {
		return nil, fmt.Errorf("连接失败: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var health HealthResponse
	if err := json.Unmarshal(body, &health); err != nil {
		return nil, fmt.Errorf("解析失败: %w", err)
	}
	return &health, nil
}

func getShipCount(baseURL string) (int, error) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(baseURL + "/api/ships")
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var ships ShipsResponse
	json.Unmarshal(body, &ships)
	return ships.Count, nil
}

func main() {
	baseURL := defaultBaseURL
	if len(os.Args) > 1 {
		baseURL = os.Args[1]
	}

	fmt.Println("========================================")
	fmt.Println("  拉格朗日AI — Go 服务检查工具")
	fmt.Println("========================================")
	fmt.Printf("  目标: %s\n\n", baseURL)

	// 健康检查
	health, err := checkHealth(baseURL)
	if err != nil {
		fmt.Printf("  ❌ 服务不可用: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("  ✅ 服务状态: %s\n", health.Status)
	fmt.Printf("  📅 时间: %s\n", health.Timestamp)
	fmt.Printf("  📚 索引: %v\n", health.IndexBuilt)

	// 舰船数量
	count, err := getShipCount(baseURL)
	if err == nil {
		fmt.Printf("  🚀 舰船: %d 艘\n", count)
	}

	fmt.Println("\n========================================")
}
