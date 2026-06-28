// MINXG Go demo — compute the 20th Fibonacci number.
package main

import "fmt"

func fib(n int) int {
	if n <= 1 {
		return n
	}
	a, b := 0, 1
	for i := 2; i <= n; i++ {
		a, b = b, a+b
	}
	return b
}

func main() {
	fmt.Printf("Go demo: fib(20) = %d\n", fib(20))
}
