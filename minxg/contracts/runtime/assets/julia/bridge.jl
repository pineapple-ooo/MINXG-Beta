# MINXG Julia bridge — real Julia source, not a Python string.
# Usage: julia minxg_bridge.jl < payload.json
# Required package: JSON (Pkg.add("JSON"))

using JSON

function run_payload(payload::Dict)
    code = get(payload, "code", "1 + 1")
    mode = get(payload, "mode", "eval")
    # Capture stdout/stderr implicitly by returning result
    result = nothing
    status = "ok"
    err_text = ""
    try
        if mode == "exec"
            Base.include_string(Main, code)
            result = "executed"
        else
            result = Base.include_string(Main, code)
        end
    catch ex
        status = "runtime_error"
        err_text = sprint(showerror, ex)
    end
    return Dict(
        "status" => status,
        "language" => "julia",
        "result" => result === nothing ? nothing : string(result),
        "stderr" => err_text,
    )
end

function main()
    line = readline(stdin)
    trimmed = strip(line)
    if isempty(trimmed)
        println(JSON.json(Dict("status" => "error", "stderr" => "empty payload")))
        return
    end
    payload = JSON.parse(trimmed)
    response = run_payload(payload)
    println(JSON.json(response))
end

main()
