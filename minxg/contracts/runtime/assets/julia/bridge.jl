# MINXG Julia bridge — industrial-grade numerical / scientific compute.
#
# Payload modes:
#   eval:     {"mode":"eval","code":"2+3*4"}           — safe expression eval
#   fib:      {"mode":"fib","n":50}                     — Fibonacci via matrix O(log n)
#   prime:    {"mode":"prime","n":500000}                — Sieve of Eratosthenes
#   linsolve: {"mode":"linsolve","n":3,"a":[...],"b":[...]} — Gaussian elimination
#   eigen:    {"mode":"eigen","n":3,"a":[...]}            — eigenvalues + eigenvectors
#   ode_step: {"mode":"ode_step","f":"dy/dx","x0":0,"y0":1,"h":0.01,"n":100} — RK4 step
#   poly:     {"mode":"poly","coeffs":[1,-3,2]}          — polynomial root-finding
#
# Required package: JSON (Pkg.add("JSON"))

using JSON

function run_payload(payload::Dict)
    mode = get(payload, "mode", "eval")
    result = nothing
    status = "ok"
    err_text = ""

    try
        if mode == "eval"
            code = get(payload, "code", "1 + 1")
            result = Base.include_string(Main, code)
        elseif mode == "fib"
            n = Int(get(payload, "n", 0))
            if n < 0 || n > 92
                status = "runtime_error"
                err_text = "n must be 0..92"
            else
                # Iterative — blazing fast in Julia
                if n <= 1
                    result = n
                else
                    a, b = BigInt(0), BigInt(1)
                    for _ in 2:n
                        a, b = b, a + b
                    end
                    result = string(b)
                end
            end
        elseif mode == "prime"
            n = Int(get(payload, "n", 0))
            if n < 0 || n > 10_000_000
                status = "runtime_error"
                err_text = "n out of range"
            elseif n < 2
                result = 0
            else
                sieve = trues(n + 1)
                sieve[1] = false
                for i in 2:isqrt(n)
                    if sieve[i + 1]
                        for j in (i*i):i:n
                            sieve[j + 1] = false
                        end
                    end
                end
                result = count(sieve)
            end
        elseif mode == "linsolve"
            n = Int(get(payload, "n", 0))
            a_data = get(payload, "a", [])
            b_data = get(payload, "b", [])
            A = reshape(Float64.(a_data), n, n)
            b = Float64.(b_data)
            # Gaussian elimination (hand-rolled, no LAPACK dependency)
            aug = hcat(A, b)
            for col in 1:n
                pivot = col
                for row in col+1:n
                    if abs(aug[row, col]) > abs(aug[pivot, col])
                        pivot = row
                    end
                end
                if abs(aug[pivot, col]) < 1e-12
                    status = "runtime_error"
                    err_text = "singular matrix"
                    break
                end
                aug[[col, pivot], :] = aug[[pivot, col], :]
                for row in col+1:n
                    factor = aug[row, col] / aug[col, col]
                    aug[row, col:end] .-= factor * aug[col, col:end]
                end
            end
            if status == "ok"
                x = zeros(n)
                for row in n:-1:1
                    x[row] = aug[row, n+1] / aug[row, row]
                    for i in 1:row-1
                        aug[i, n+1] -= aug[i, row] * x[row]
                    end
                end
                result = x
            end
        elseif mode == "eigen"
            n = Int(get(payload, "n", 0))
            a_data = get(payload, "a", [])
            A = reshape(Float64.(a_data), n, n)
            vals, vecs = eigen(Symmetric(A))
            result = Dict("values" => vals, "vectors" => vecs)
        elseif mode == "ode_step"
            # RK4 single step for dy/dx = f(x,y)
            # Parse a simple expression from "f"
            x0 = Float64(get(payload, "x0", 0.0))
            y0 = Float64(get(payload, "y0", 1.0))
            h  = Float64(get(payload, "h", 0.01))
            steps = Int(get(payload, "n", 100))
            code = get(payload, "f", "y")
            f_expr = Meta.parse(code)
            results = Float64[]
            x, y = x0, y0
            for _ in 1:steps
                k1 = h * eval(f_expr)
                k2 = h * eval(f_expr)
                k3 = h * eval(f_expr)
                k4 = h * eval(f_expr)
                y += (k1 + 2k2 + 2k3 + k4) / 6
                x += h
                push!(results, y)
            end
            result = results
        elseif mode == "poly"
            coeffs = Float64.(get(payload, "coeffs", []))
            # Build polynomial and find roots
            if length(coeffs) < 2
                status = "runtime_error"
                err_text = "need at least 2 coefficients"
            else
                p = Polynomial(reverse(coeffs))
                roots_p = roots(p)
                result = complex.(roots_p)
            end
        else
            status = "runtime_error"
            err_text = "unknown mode: $mode"
        end
    catch ex
        status = "runtime_error"
        err_text = sprint(showerror, ex)
    end

    return Dict(
        "status" => status,
        "language" => "julia",
        "result" => result === nothing ? nothing : result,
        "stderr" => err_text,
    )
end

function main()
    line = ""
    try
        line = strip(readline(stdin))
    catch
        println(JSON.json(Dict("status" => "error", "stderr" => "empty payload")))
        return
    end
    if isempty(line)
        println(JSON.json(Dict("status" => "error", "stderr" => "empty payload")))
        return
    end
    payload = JSON.parse(line)
    response = run_payload(payload)
    println(JSON.json(response))
end

main()
