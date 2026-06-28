# MINXG Julia demo — sum the first N integers using a fast formula.
# This file is executed by the Julia adapter when no custom code is supplied.

function sum_to(n::Int)
    return n * (n + 1) ÷ 2
end

n = 100
println("Julia demo: sum(1:$n) = $(sum_to(n))")
