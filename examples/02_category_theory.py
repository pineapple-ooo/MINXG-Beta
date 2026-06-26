"""
02 — Category Theory: morphisms, monads, and the Yoneda embedding.

Type-safe operator composition with mathematical guarantees.
"""
import minxg.cat as cat
from minxg.cat import Maybe, MaybeM, State, IdentityM, yoneda_embedding

f = cat.Morphism("int_to_str", (cat.Type("int"),), cat.Type("string"), str)
g = cat.Morphism("str_to_len", (cat.Type("string"),), cat.Type("int"), len)
h = cat.Morphism("int_to_float", (cat.Type("int"),), cat.Type("float"), float)
pipeline = f >> g
assert pipeline(42) == 2
assert pipeline(12345) == 5
print(f"pipeline(42) = {pipeline(42)}")

try:
    bad = f >> h  
    assert False, "should have raised TypeError"
except TypeError as e:
    print(f"type error caught: {e}")

m1 = Maybe.just(5)
m2 = m1.fmap(lambda x: x * 2)
m3 = Maybe.nothing().fmap(lambda x: x * 2)
print(f"Just(5).fmap(*2) = {m2}")
print(f"Nothing.fmap(*2) = {m3}")
assert m2.is_just and m2.value == 10
assert not m3.is_just

program = (
    State.get()
    .bind(lambda x: State.put(x * 10))
    .bind(lambda _: State.get())
)
final_state, result = program.run(5)
print(f"State monad: start=5, result={result}, end={final_state}")
assert result == 50 and final_state == 50

def double(x):
    return IdentityM.unit(x * 2)

id_monad_law_left = IdentityM.unit(7).bind(double) == double(7)
id_monad_law_right = IdentityM.unit(7).bind(IdentityM.unit) == IdentityM.unit(7)
print(f"IdentityM monad left-identity law: {id_monad_law_left}")
print(f"IdentityM monad right-identity law: {id_monad_law_right}")
assert id_monad_law_left and id_monad_law_right

def op(x):
    return x * x + 1

representation = yoneda_embedding(op, [0, 1, 2, 3, 5, 10])
print(f"yoneda encoding of x²+1 on [0,1,2,3,5,10] = {representation}")
assert representation == [1, 2, 5, 10, 26, 101]

print("\nall assertions passed")
