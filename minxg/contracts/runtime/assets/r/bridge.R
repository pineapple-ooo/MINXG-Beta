# MINXG R bridge — real R source, not a Python string.
# Usage: Rscript minxg_bridge.R < payload.json
# Required package: jsonlite  (install.packages("jsonlite"))

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  cat('{"status":"runtime_error","language":"r","stderr":"R package jsonlite is required: install.packages(\\"jsonlite\\")"}\n')
  quit(status = 1)
}

payload <- jsonlite::fromJSON(readLines(file("stdin"), n = 1))
code <- payload$code
if (is.null(code)) {
  code <- "1 + 1"
}

result <- NULL
status <- "ok"
err_text <- ""

# Evaluate in a fresh environment to avoid cross-run pollution
eval_env <- new.env()
tryCatch(
  {
    result <- eval(parse(text = code), envir = eval_env)
  },
  error = function(e) {
    assign("status", "runtime_error", envir = parent.env(environment()))
    assign("err_text", conditionMessage(e), envir = parent.env(environment()))
  }
)

response <- list(
  status = status,
  language = "r",
  result = if (!is.null(result)) as.character(result) else NULL,
  stderr = err_text
)
cat(jsonlite::toJSON(response, auto_unbox = TRUE, null = "null"), "\n")
