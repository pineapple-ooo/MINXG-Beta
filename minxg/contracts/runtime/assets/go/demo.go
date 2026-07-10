// MINXG Go demo — industrial benchmarks.
package main

import "fmt"

type mat2 [2][2]int64

func m2m(x, y mat2) mat2 {
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

func m2p(b mat2, n int64) mat2 {
	r := mat2{{1, 0}, {0, 1}}
	for n > 0 {
		if n&1 == 1 {
			r = m2m(r, b)
		}
		b = m2m(b, b)
		n >>= 1
	}
	return r
}

func fib(n int64) int64 {
	if n <= 0 { return 0 }
	if n == 1 { return 1 }
	Q := mat2{{1, 1}, {1, 0}}
	R := m2p(Q, n-1)
	return R[0][0]
}

func primes(n int64) int64 {
	if n < 2 { return 0 }
	s := make([]bool, n+1)
	c := int64(0)
	for i := int64(2); i <= n; i++ {
		if !s[i] {
			c++
			for j := i * i; j <= n; j += i {
				s[j] = true
			}
		}
	}
	return c
}

func main() {
	f := fib(92)
	p := primes(1000000)
	fmt.Printf("{\"fib92\":%d,\"prime1M\":%d}\n", f, p)
}
