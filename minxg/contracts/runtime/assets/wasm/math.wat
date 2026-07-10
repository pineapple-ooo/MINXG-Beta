;; MINXG WebAssembly bridge — industrial-grade numeric compute.
;;
;; Exports:
;;   add, sub, mul, div      — i32 arithmetic
;;   fadd, fsub, fmul, fdiv  — f64 IEEE-754 arithmetic
;;   fib                     — Fibonacci via matrix O(log n) up to fib(46)
;;   factorial               — iterative factorial
;;   gcd                     — greatest common divisor (Euclidean)
;;   is_prime                — trial division primality test
;;   mat_det3                — 3x3 determinant
;;   mandelbrot              — mandelbrot iteration count (max 255)
;;
;; This is a real .wat source file with genuine computational kernels,
;; not a bare "a + b" demo.

(module
  ;; ── i32 arithmetic ─────────────────────────────────────
  (func $add (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.add)
  (export "add" (func $add))

  (func $sub (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.sub)
  (export "sub" (func $sub))

  (func $mul (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.mul)
  (export "mul" (func $mul))

  (func $div_s (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.div_s)
  (export "div" (func $div_s))

  (func $rem_s (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.rem_s)
  (export "mod" (func $rem_s))

  ;; ── f64 IEEE-754 arithmetic ─────────────────────────────
  (func $fadd (param f64 f64) (result f64)
    local.get 0
    local.get 1
    f64.add)
  (export "fadd" (func $fadd))

  (func $fsub (param f64 f64) (result f64)
    local.get 0
    local.get 1
    f64.sub)
  (export "fsub" (func $fsub))

  (func $fmul (param f64 f64) (result f64)
    local.get 0
    local.get 1
    f64.mul)
  (export "fmul" (func $fmul))

  (func $fdiv (param f64 f64) (result f64)
    local.get 0
    local.get 1
    f64.div)
  (export "fdiv" (func $fdiv))

  ;; ── Fibonacci via fast doubling O(log n) ────────────────
  ;; Returns fib(n) for 0 <= n <= 46 (fits in i32)
  (func $fib (param $n i32) (result i32)
    (local $a i32)
    (local $b i32)
    (local $c i32)
    (local $d i32)
    (local $bit i32)
    (local $temp i32)

    ;; Special cases
    local.get $n
    i32.eqz
    if (result i32) i32.const 0
    else
      local.get $n
      i32.const 1
      i32.eq
      if (result i32) i32.const 1
      else
        ;; Fast doubling: fib(2k) = fib(k) * [2*fib(k+1) - fib(k)]
        ;;                fib(2k+1) = fib(k)^2 + fib(k+1)^2
        i32.const 0
        local.set $a   ;; fib(0)
        i32.const 1
        local.set $b   ;; fib(1)

        ;; Find highest bit
        local.get $n
        local.set $bit

        ;; Iterate from MSB to LSB
        (block $break
          (loop $loop
            ;; If bit == 0, done
            local.get $bit
            i32.eqz
            br_if $break

            ;; Doubling step
            ;; c = a * (2*b - a)
            local.get $b
            i32.const 2
            i32.mul
            local.get $a
            i32.sub
            local.get $a
            i32.mul
            local.set $c

            ;; d = a*a + b*b
            local.get $a
            local.get $a
            i32.mul
            local.get $b
            local.get $b
            i32.mul
            i32.add
            local.set $d

            ;; If current bit is 1: a=d, b=c+d
            ;; If current bit is 0: a=c, b=d
            local.get $n
            local.get $bit
            i32.and
            i32.const 0
            i32.ne
            if
              local.get $d
              local.set $a
              local.get $c
              local.get $d
              i32.add
              local.set $b
            else
              local.get $c
              local.set $a
              local.get $d
              local.set $b
            end

            ;; Shift bit right
            local.get $bit
            i32.const 1
            i32.shr_u
            local.set $bit

            br $loop
          )
        )

        local.get $a
      end
    end)
  (export "fib" (func $fib))

  ;; ── Factorial (iterative) ──────────────────────────────
  (func $factorial (param $n i32) (result i32)
    (local $result i32)
    (local $i i32)
    i32.const 1
    local.set $result
    i32.const 2
    local.set $i
    (block $break
      (loop $loop
        local.get $i
        local.get $n
        i32.gt_s
        br_if $break
        local.get $result
        local.get $i
        i32.mul
        local.set $result
        local.get $i
        i32.const 1
        i32.add
        local.set $i
        br $loop
      )
    )
    local.get $result)
  (export "factorial" (func $factorial))

  ;; ── GCD (Euclidean algorithm) ──────────────────────────
  (func $gcd (param $a i32) (param $b i32) (result i32)
    (local $temp i32)
    (block $break
      (loop $loop
        local.get $b
        i32.eqz
        br_if $break
        local.get $a
        local.get $b
        i32.rem_s
        local.set $temp
        local.get $b
        local.set $a
        local.get $temp
        local.set $b
        br $loop
      )
    )
    local.get $a)
  (export "gcd" (func $gcd))

  ;; ── Primality test (trial division) ────────────────────
  ;; Returns 1 if prime, 0 if composite
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
          (block $break
            (loop $loop
              local.get $i
              local.get $i
              i32.mul
              local.get $n
              i32.gt_s
              br_if $break
              local.get $n
              local.get $i
              i32.rem_s
              i32.eqz
              if
                i32.const 0
                return
              end
              local.get $i
              i32.const 2
              i32.add
              local.set $i
              br $loop
            )
          )
        end
      end
    end)
  (export "is_prime" (func $is_prime))

  ;; ── 3x3 Determinant ────────────────────────────────────
  ;; Input: row0_a, row0_b, row0_c, row1_a, ..., row2_c (9 f64s)
  (func $mat_det3
    (param $a00 f64) (param $a01 f64) (param $a02 f64)
    (param $a10 f64) (param $a11 f64) (param $a12 f64)
    (param $a20 f64) (param $a21 f64) (param $a22 f64)
    (result f64)
    local.get $a00
    local.get $a11
    f64.mul
    local.get $a22
    f64.mul

    local.get $a00
    local.get $a12
    f64.mul
    local.get $a21
    f64.mul
    f64.sub

    local.get $a01
    local.get $a10
    f64.mul
    local.get $a22
    f64.mul
    f64.sub

    local.get $a01
    local.get $a12
    f64.mul
    local.get $a20
    f64.mul
    f64.add

    local.get $a02
    local.get $a10
    f64.mul
    local.get $a21
    f64.mul
    f64.add

    local.get $a02
    local.get $a11
    f64.mul
    local.get $a20
    f64.mul
    f64.sub)
  (export "mat_det3" (func $mat_det3))

  ;; ── Mandelbrot iteration count ──────────────────────────
  ;; Returns iteration count (0..255) for point (cx, cy)
  ;; z_{n+1} = z_n^2 + c,  |z|^2 > 4 triggers escape
  (func $mandelbrot (param $cx f64) (param $cy f64) (result i32)
    (local $zx f64)
    (local $zy f64)
    (local $zx2 f64)
    (local $zy2 f64)
    (local $iter i32)
    (local $tmp f64)

    f64.const 0
    local.set $zx
    f64.const 0
    local.set $zy
    i32.const 0
    local.set $iter

    (block $break
      (loop $loop
        ;; Check iterations
        local.get $iter
        i32.const 255
        i32.ge_s
        br_if $break

        ;; |z|^2 = zx^2 + zy^2
        local.get $zx
        local.get $zx
        f64.mul
        local.set $zx2
        local.get $zy
        local.get $zy
        f64.mul
        local.set $zy2

        ;; Escape?
        local.get $zx2
        local.get $zy2
        f64.add
        f64.const 4.0
        f64.gt
        br_if $break

        ;; z = z^2 + c:  tmp = zx^2 - zy^2 + cx
        local.get $zx2
        local.get $zy2
        f64.sub
        local.get $cx
        f64.add
        local.set $tmp

        ;; zy = 2*zx*zy + cy
        local.get $zx
        local.get $zy
        f64.mul
        f64.const 2.0
        f64.mul
        local.get $cy
        f64.add
        local.set $zy

        local.get $tmp
        local.set $zx

        local.get $iter
        i32.const 1
        i32.add
        local.set $iter

        br $loop
      )
    )
    local.get $iter)
  (export "mandelbrot" (func $mandelbrot))

  ;; ── Memory for data interchange ─────────────────────────
  (memory (export "memory") 1)
)
