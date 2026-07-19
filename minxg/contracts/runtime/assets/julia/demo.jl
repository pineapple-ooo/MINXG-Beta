# MINXG Julia demo — industrial numerical benchmarks.
#
# Demonstrates: Fibonacci (BigInt), prime sieve, linear solve, eigenvalues.

println("Julia demo: computing benchmarks...")

# Fibonacci(30) — iterative
function fib(n::Int)
    n <= 0 && return 0
    n == 1 && return 1
    a, b = 0, 1
    for _ in 2:n
        a, b = b, a + b
    end
    return b
end

# Prime sieve
function prime_count(n::Int)
    n < 2 && return 0
    sieve = trues(n + 1)
    sieve[1] = false
    for i in 2:isqrt(n)
        sieve[i + 1] && (for j in (i*i):i:n; sieve[j + 1] = false; end)
    end
    return count(sieve)
end

println("fib(30) = ", fib(30))
println("primes up to 1M = ", prime_count(1_000_000))

# 3x3 linear solve
A = [1.0 2.0 3.0; 0.0 1.0 4.0; 5.0 6.0 0.0]
b = [14.0, 13.0, 9.0]
x = A \ b
println("Ax=b => x = $x")

# Fibonacci(92) with BigInt
function fib_big(n::Int)
    n <= 0 && return BigInt(0)
    n == 1 && return BigInt(1)
    a, b = BigInt(0), BigInt(1)
    for _ in 2:n
        a, b = b, a + b
    end
    return b
end
println("fib(92) = ", fib_big(92))
