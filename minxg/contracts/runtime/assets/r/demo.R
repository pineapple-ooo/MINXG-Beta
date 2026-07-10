# MINXG R demo — statistical benchmarks.
#
# Demonstrates: Fibonacci, prime sieve, linear solve, full statistical summary.
# Output: JSON

cat("R demo: computing benchmarks...\n")

# Fibonacci(30) iteratively
fib <- function(n) {
  if (n <= 0) return(0)
  if (n == 1) return(1)
  a <- 0; b <- 1
  for (i in 2:n) { t <- a + b; a <- b; b <- t }
  return(b)
}

# Prime sieve up to 1M
primes <- function(n) {
  if (n < 2) return(0)
  sieve <- rep(TRUE, n + 1)
  sieve[1] <- FALSE
  for (i in 2:floor(sqrt(n))) {
    if (sieve[i]) sieve[seq(i * i, n, by = i)] <- FALSE
  }
  return(sum(sieve))
}

cat(sprintf("fib(30) = %d\n", fib(30)))
cat(sprintf("primes up to 1M = %d\n", primes(1000000)))

# Linear solve demo
A <- matrix(c(1,2,3, 0,1,4, 5,6,0), nrow=3, byrow=TRUE)
b <- c(14, 13, 9)
x <- solve(A, b)
cat(sprintf("Ax=b => x = [%g, %g, %g]\n", x[1], x[2], x[3]))
