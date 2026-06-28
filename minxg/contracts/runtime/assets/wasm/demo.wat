;; MINXG WebAssembly demo — sum of 1..N using a tiny loop.
;; The Python adapter passes N as an argument and invokes $sum_to.

(module
  (func $sum_to (param $n i32) (result i32)
    (local $i i32)
    (local $acc i32)
    i32.const 0
    local.set $acc
    i32.const 1
    local.set $i
    (block $done
      (loop $step
        local.get $i
        local.get $n
        i32.gt_s
        br_if $done
        local.get $acc
        local.get $i
        i32.add
        local.set $acc
        local.get $i
        i32.const 1
        i32.add
        local.set $i
        br $step
      )
    )
    local.get $acc
  )
  (export "sum_to" (func $sum_to))
)
