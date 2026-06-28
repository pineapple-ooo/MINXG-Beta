% MINXG Datalog demo — find all reachable nodes and even numbers up to 10.

#const top = 10.
number(1..top).
even(N) :- number(N), N \\ 2 == 0.

edge(a, b).
edge(b, c).
edge(c, d).
reachable(X, Y) :- edge(X, Y).
reachable(X, Y) :- edge(X, Z), reachable(Z, Y).

#show even/1.
#show reachable/2.
