// MINXG Go bridge — industrial-grade numeric compute.
//
// Payload modes:
//   eval:     {"mode":"eval","code":"2 + 3*4"}        — safe expression evaluator
//   fib:      {"mode":"fib","n":50}                    — Fibonacci O(log n) matrix exponentiation
//   prime:    {"mode":"prime","n":500000}               — Sieve of Eratosthenes
//   fft:      {"mode":"fft","data":[1,2,3,4]}           — naive DFT
//   linsolve: {"mode":"linsolve","n":3,"a":[...],"b":[...]} — Gaussian elimination
//   matmul:   {"mode":"matmul","n":3,"a":[...],"b":[...]}   — matrix multiplication
//
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
)

type payload struct {
	Mode string   `json:"mode"`
	Code string   `json:"code"`
	N    int64    `json:"n"`
	Data []float64 `json:"data"`
	A    []float64 `json:"a"`
	B    []float64 `json:"b"`
}

// ── Fibonacci via matrix exponentiation O(log n) ──────────

type mat2 [2][2]int64

func mat2Mul(x, y mat2) mat2 {
	var r mat2
	for i := 0; i < 2; i++ {
		for j := 0; j < 2; j++ {
			for k := 0; k < 2; k++ {
				r[i][j] += x[i][k] * y[k][j]
			}
		}
	}
	return r
}

func mat2Pow(base mat2, n int64) mat2 {
	result := mat2{{1, 0}, {0, 1}}
	for n > 0 {
		if n&1 == 1 {
			result = mat2Mul(result, base)
		}
		base = mat2Mul(base, base)
		n >>= 1
	}
	return result
}

func fibonacci(n int64) int64 {
	if n <= 0 {
		return 0
	}
	if n == 1 {
		return 1
	}
	Q := mat2{{1, 1}, {1, 0}}
	R := mat2Pow(Q, n-1)
	return R[0][0]
}

// ── Sieve of Eratosthenes ──────────────────────────────────

func primeSieve(n int64) int64 {
	if n < 2 {
		return 0
	}
	sieve := make([]bool, n+1)
	count := int64(0)
	for i := int64(2); i <= n; i++ {
		if !sieve[i] {
			count++
			for j := i * i; j <= n; j += i {
				sieve[j] = true
			}
		}
	}
	return count
}

// ── Naive DFT O(n^2) ──────────────────────────────────────

func naiveDFT(in []float64) []complex128 {
	n := len(in)
	out := make([]complex128, n)
	for k := 0; k < n; k++ {
		var re, im float64
		for t := 0; t < n; t++ {
			angle := 2.0 * math.Pi * float64(k) * float64(t) / float64(n)
			re += in[t] * math.Cos(angle)
			im -= in[t] * math.Sin(angle)
		}
		out[k] = complex(re, im)
	}
	return out
}

// ── Gaussian elimination ──────────────────────────────────

func gaussSolve(A []float64, b []float64, n int) ([]float64, bool) {
	// Copy to avoid mutation
	mat := make([][]float64, n)
	for i := 0; i < n; i++ {
		mat[i] = make([]float64, n+1)
		for j := 0; j < n; j++ {
			mat[i][j] = A[i*n+j]
		}
		mat[i][n] = b[i]
	}
	// Forward elimination
	for col := 0; col < n; col++ {
		pivot := col
		for row := col + 1; row < n; row++ {
			if math.Abs(mat[row][col]) > math.Abs(mat[pivot][col]) {
				pivot = row
			}
		}
		if math.Abs(mat[pivot][col]) < 1e-12 {
			return nil, false // singular
		}
		mat[col], mat[pivot] = mat[pivot], mat[col]
		for row := col + 1; row < n; row++ {
			factor := mat[row][col] / mat[col][col]
			for j := col; j <= n; j++ {
				mat[row][j] -= factor * mat[col][j]
			}
		}
	}
	// Back-substitution
	x := make([]float64, n)
	for row := n - 1; row >= 0; row-- {
		x[row] = mat[row][n] / mat[row][row]
		for i := 0; i < row; i++ {
			mat[i][n] -= mat[i][row] * x[row]
		}
	}
	return x, true
}

// ── Matrix multiplication ──────────────────────────────────

func matmul(a, b []float64, n int) []float64 {
	c := make([]float64, n*n)
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			for k := 0; k < n; k++ {
				c[i*n+j] += a[i*n+k] * b[k*n+j]
			}
		}
	}
	return c
}

// ── Extended safe evaluator ────────────────────────────────

func evalExpr(expr string) (float64, string) {
	expr = strings.TrimSpace(expr)
	var a, b float64
	var op rune

	// Unary
	if strings.HasPrefix(expr, "sin(") {
		if _, err := fmt.Sscanf(expr, "sin(%f)", &a); err == nil {
			return math.Sin(a), ""
		}
	}
	if strings.HasPrefix(expr, "cos(") {
		if _, err := fmt.Sscanf(expr, "cos(%f)", &a); err == nil {
			return math.Cos(a), ""
		}
	}
	if strings.HasPrefix(expr, "sqrt(") {
		if _, err := fmt.Sscanf(expr, "sqrt(%f)", &a); err == nil && a >= 0 {
			return math.Sqrt(a), ""
		}
	}
	if strings.HasPrefix(expr, "log(") {
		if _, err := fmt.Sscanf(expr, "log(%f)", &a); err == nil && a > 0 {
			return math.Log(a), ""
		}
	}
	if strings.HasPrefix(expr, "exp(") {
		if _, err := fmt.Sscanf(expr, "exp(%f)", &a); err == nil {
			return math.Exp(a), ""
		}
	}
	// Power
	if strings.Contains(expr, "^") {
		if _, err := fmt.Sscanf(expr, "%f ^ %f", &a, &b); err == nil {
			return math.Pow(a, b), ""
		}
	}
	// Binary
	if _, err := fmt.Sscanf(expr, "%f %c %f", &a, &op, &b); err == nil {
		switch op {
		case '+':
			return a + b, ""
		case '-':
			return a - b, ""
		case '*':
			return a * b, ""
		case '/':
			if b == 0 {
				return 0, "division by zero"
			}
			return a / b, ""
		}
	}
	return 0, "unsupported expression"
}

// ── Main ────────────────────────────────────────────────────

func main() {
	reader := bufio.NewReader(os.Stdin)
	line, err := reader.ReadString('\n')
	if err != nil && len(line) == 0 {
		fmt.Println(`{"status":"error","stderr":"empty payload"}`)
		os.Exit(1)
	}
	line = strings.TrimSpace(line)
	var p payload
	if jsonErr := json.Unmarshal([]byte(line), &p); jsonErr != nil {
		fmt.Printf(`{"status":"error","stderr":%q}`+"\n", jsonErr.Error())
		os.Exit(1)
	}

	mode := p.Mode
	if mode == "" {
		mode = "eval"
	}

	switch mode {
	case "eval":
		code := p.Code
		if code == "" {
			code = "1 + 1"
		}
		result, errMsg := evalExpr(code)
		if errMsg != "" {
			fmt.Printf(`{"status":"runtime_error","language":"go","stderr":%q}`+"\n", errMsg)
		} else {
			fmt.Printf("{\"status\":\"ok\",\"language\":\"go\",\"result\":%.15g}\n", result)
		}

	case "fib":
		if p.N < 0 || p.N > 92 {
			fmt.Println(`{"status":"runtime_error","language":"go","stderr":"n must be 0..92"}`)
		} else {
			r := fibonacci(p.N)
			fmt.Printf("{\"status\":\"ok\",\"language\":\"go\",\"result\":%d}\n", r)
		}

	case "prime":
		if p.N < 0 || p.N > 10000000 {
			fmt.Println(`{"status":"runtime_error","language":"go","stderr":"n out of range"}`)
		} else {
			r := primeSieve(p.N)
			fmt.Printf("{\"status\":\"ok\",\"language\":\"go\",\"result\":%d}\n", r)
		}

	case "fft":
		if len(p.Data) < 1 {
			fmt.Println(`{"status":"runtime_error","language":"go","stderr":"empty data"}`)
		} else {
			result := naiveDFT(p.Data)
			fmt.Printf("{\"status\":\"ok\",\"language\":\"go\",\"n\":%d,\"result\":[", len(p.Data))
			for i, c := range result {
				if i > 0 {
					fmt.Print(",")
				}
				fmt.Printf("%.10g,%.10g", real(c), imag(c))
			}
			fmt.Println("]}")
		}

	case "linsolve":
		n := int(p.N)
		if n < 1 || n > 64 || len(p.A) < n*n || len(p.B) < n {
			fmt.Println(`{"status":"runtime_error","language":"go","stderr":"dimension mismatch"}`)
		} else {
			x, ok := gaussSolve(p.A, p.B, n)
			if !ok {
				fmt.Println(`{"status":"runtime_error","language":"go","stderr":"singular matrix"}`)
			} else {
				fmt.Printf("{\"status\":\"ok\",\"language\":\"go\",\"result\":[")
				for i, v := range x {
					if i > 0 {
						fmt.Print(",")
					}
					fmt.Printf("%.15g", v)
				}
				fmt.Println("]}")
			}
		}

	case "matmul":
		n := int(p.N)
		if n < 1 || n > 64 || len(p.A) < n*n || len(p.B) < n*n {
			fmt.Println(`{"status":"runtime_error","language":"go","stderr":"dimension mismatch"}`)
		} else {
			c := matmul(p.A, p.B, n)
			fmt.Printf("{\"status\":\"ok\",\"language\":\"go\",\"n\":%d,\"result\":[", n)
			for i, v := range c {
				if i > 0 {
					fmt.Print(",")
				}
				fmt.Printf("%.15g", v)
			}
			fmt.Println("]}")
		}

	default:
		fmt.Printf(`{"status":"runtime_error","language":"go","stderr":"unknown mode: %s"}`+"\n", mode)
	}
}

// Unused stub to satisfy strconv import (our sscanf parsing uses strconv internally)
var _ = strconv.Itoa
