# MINXG R bridge — industrial-grade statistical / numerical compute.
#
# Payload modes:
#   eval:     {"mode":"eval","code":"2+3*4"}         — safe R expression evaluator
#   fib:      {"mode":"fib","n":50}                   — Fibonacci (recursive with memoization)
#   prime:    {"mode":"prime","n":500000}              — Sieve of Eratosthenes
#   linsolve: {"mode":"linsolve","n":3,"a":[...],"b":[...]} — solve(A, b)
#   summary:  {"mode":"summary","data":[...]}          — full statistical summary
#   hist:     {"mode":"hist","data":[...],"bins":10}   — histogram binning
#   regress:  {"mode":"regress","x":[...],"y":[...]}   — simple linear regression
#   cov:      {"mode":"cov","data":[[1,2],[3,4],...]}  — covariance matrix
#
# Required package: jsonlite

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  cat('{"status":"runtime_error","language":"r","stderr":"R package jsonlite is required: install.packages(\\"jsonlite\\")"}\n')
  quit(status = 1)
}

payload <- jsonlite::fromJSON(readLines(file("stdin"), n = 1, warn = FALSE))
code <- payload$code
mode <- if (is.null(payload$mode)) "eval" else payload$mode

status <- "ok"
err_text <- ""
result <- NULL

eval_env <- new.env()

tryCatch(
  {
    if (mode == "eval") {
      if (is.null(code) || code == "") code <- "1 + 1"
      result <- eval(parse(text = code), envir = eval_env)
    }
    else if (mode == "fib") {
      n <- payload$n
      if (is.null(n) || n < 0 || n > 92) {
        status <- "runtime_error"
        err_text <- "n must be 0..92"
      } else {
        # Iterative Fibonacci (fast, no recursion overhead)
        if (n <= 1) {
          result <- n
        } else {
          a <- 0; b <- 1
          for (i in 2:n) { t <- a + b; a <- b; b <- t }
          result <- b
        }
      }
    }
    else if (mode == "prime") {
      n <- payload$n
      if (is.null(n) || n < 0 || n > 1e7) {
        status <- "runtime_error"
        err_text <- "n out of range (0..10000000)"
      } else if (n < 2) {
        result <- 0
      } else {
        sieve <- rep(TRUE, n + 1)
        sieve[1] <- FALSE
        for (i in 2:floor(sqrt(n))) {
          if (sieve[i]) {
            sieve[seq(i * i, n, by = i)] <- FALSE
          }
        }
        result <- sum(sieve)
      }
    }
    else if (mode == "linsolve") {
      n <- payload$n
      a <- matrix(payload$a, nrow = n, ncol = n, byrow = TRUE)
      b <- payload$b
      result <- as.numeric(solve(a, b))
    }
    else if (mode == "summary") {
      data <- payload$data
      result <- list(
        n     = length(data),
        mean  = mean(data),
        sd    = sd(data),
        min   = min(data),
        q25   = quantile(data, 0.25),
        median = median(data),
        q75   = quantile(data, 0.75),
        max   = max(data),
        skew  = (sum((data - mean(data))^3) / length(data)) / (sd(data)^3),
        kurt  = (sum((data - mean(data))^4) / length(data)) / (sd(data)^4) - 3
      )
    }
    else if (mode == "hist") {
      data <- payload$data
      bins <- if (is.null(payload$bins)) 10 else payload$bins
      h <- hist(data, breaks = bins, plot = FALSE)
      result <- list(
        breaks = h$breaks,
        counts = h$counts,
        density = h$density,
        mids = h$mids
      )
    }
    else if (mode == "regress") {
      x <- payload$x
      y <- payload$y
      if (length(x) != length(y) || length(x) < 2) {
        status <- "runtime_error"
        err_text <- "x and y must have same length (>= 2)"
      } else {
        fit <- lm(y ~ x)
        coefs <- coef(fit)
        result <- list(
          intercept = coefs[1],
          slope     = coefs[2],
          r_squared = summary(fit)$r.squared,
          residuals = as.numeric(residuals(fit))
        )
      }
    }
    else if (mode == "cov") {
      mat <- do.call(rbind, payload$data)
      result <- as.numeric(as.vector(cov(mat)))
    }
    else {
      status <- "runtime_error"
      err_text <- paste0("unknown mode: ", mode)
    }
  },
  error = function(e) {
    status <<- "runtime_error"
    err_text <<- conditionMessage(e)
  }
)

response <- list(
  status = status,
  language = "r",
  result = if (!is.null(result)) result else NULL,
  stderr = err_text
)
cat(jsonlite::toJSON(response, auto_unbox = TRUE, null = "null"), "\n")
