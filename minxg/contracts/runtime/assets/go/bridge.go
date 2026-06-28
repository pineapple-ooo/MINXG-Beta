// MINXG Go bridge — real Go source.
// Reads a JSON payload from stdin, evaluates a simple arithmetic expression,
// and prints a JSON response. The Python adapter can also "go run" custom code.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

type payload struct {
	Code string `json:"code"`
}

func evalExpr(expr string) (int64, string) {
	expr = strings.TrimSpace(expr)
	var a, b int64
	var op rune
	if _, err := fmt.Sscanf(expr, "%d %c %d", &a, &op, &b); err != nil {
		return 0, "only simple 'a op b' arithmetic is supported in Go bridge"
	}
	switch op {
	case '+':
		return a + b, ""
	case '-':
		return a - b, ""
	case '*':
		return a * b, ""
	case '/':
		if b == 0 {
			return 0, "divide by zero"
		}
		return a / b, ""
	}
	return 0, "unsupported operator"
}

func main() {
	reader := bufio.NewReader(os.Stdin)
	line, err := reader.ReadString('\n')
	if err != nil && len(line) == 0 {
		fmt.Println(`{"status":"error","stderr":"empty payload"}`)
		os.Exit(1)
	}
	var p payload
	if err := json.Unmarshal([]byte(line), &p); err != nil {
		fmt.Printf("{\"status\":\"error\",\"stderr\":%q}\n", err.Error())
		os.Exit(1)
	}
	result, msg := evalExpr(p.Code)
	if msg != "" {
		fmt.Printf("{\"status\":\"runtime_error\",\"language\":\"go\",\"stderr\":%q}\n", msg)
	} else {
		fmt.Printf("{\"status\":\"ok\",\"language\":\"go\",\"result\":%d}\n", result)
	}
}
