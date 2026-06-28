;; MINXG WebAssembly bridge — real WAT source.
;; Provides arithmetic exports that the Python adapter can invoke.

(module
  (func $add (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.add)
  (export "add" (func $add))

  (func $sub (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.sub)
  (export "sub" (func $sub))

  (func $mul (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.mul)
  (export "mul" (func $mul))
)
