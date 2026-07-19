;; MINXG WebAssembly demo — Mandelbrot set computation.
;;
;; Exports mandelbrot() so that the host can sample the fractal.
;; Also exports fib() and is_prime() for numeric benchmarks.

(module
  ;; Fibonacci iterative
  (func $fib (param $n i32) (result i32)
    (local $a i32)
    (local $b i32)
    (local $i i32)
    (local $t i32)
    i32.const 0
    local.set $a
    i32.const 1
    local.set $b
    i32.const 1
    local.set $i
    (block $brk
      (loop $lp
        local.get $i
        local.get $n
        i32.gt_s
        br_if $brk
        local.get $a
        local.get $b
        i32.add
        local.set $t
        local.get $b
        local.set $a
        local.get $t
        local.set $b
        local.get $i
        i32.const 1
        i32.add
        local.set $i
        br $lp))
    local.get $a)
  (export "fib" (func $fib))

  ;; Primality test
  (func $is_prime (param $n i32) (result i32)
    (local $i i32)
    local.get $n
    i32.const 2
    i32.lt_s
    if (result i32) i32.const 0
    else
      local.get $n
      i32.const 2
      i32.eq
      if (result i32) i32.const 1
      else
        local.get $n
        i32.const 2
        i32.rem_s
        i32.eqz
        if (result i32) i32.const 0
        else
          i32.const 3
          local.set $i
          i32.const 1
          (block $brk
            (loop $lp
              local.get $i
              local.get $i
              i32.mul
              local.get $n
              i32.gt_s
              br_if $brk
              local.get $n
              local.get $i
              i32.rem_s
              i32.eqz
              if i32.const 0 return end
              local.get $i
              i32.const 2
              i32.add
              local.set $i
              br $lp))
        end
      end
    end)
  (export "is_prime" (func $is_prime))

  ;; Mandelbrot iteration count
  (func $mandelbrot (param $cx f64) (param $cy f64) (result i32)
    (local $zx f64) (local $zy f64) (local $iter i32)
    (local $zx2 f64) (local $zy2 f64) (local $tmp f64)
    f64.const 0 local.set $zx
    f64.const 0 local.set $zy
    i32.const 0 local.set $iter
    (block $brk
      (loop $lp
        local.get $iter i32.const 255 i32.ge_s br_if $brk
        local.get $zx local.get $zx f64.mul local.set $zx2
        local.get $zy local.get $zy f64.mul local.set $zy2
        local.get $zx2 local.get $zy2 f64.add f64.const 4 f64.gt br_if $brk
        local.get $zx2 local.get $zy2 f64.sub local.get $cx f64.add local.set $tmp
        local.get $zx local.get $zy f64.mul f64.const 2 f64.mul local.get $cy f64.add local.set $zy
        local.get $tmp local.set $zx
        local.get $iter i32.const 1 i32.add local.set $iter
        br $lp))
    local.get $iter)
  (export "mandelbrot" (func $mandelbrot))

  (memory (export "memory") 1)
)
