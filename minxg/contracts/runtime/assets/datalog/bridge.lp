% MINXG Datalog bridge — real ASP/Datalog source.
% It provides reusable predicates that user scripts can extend.

% Type declarations for cleaner models
#const top = 100.

number(1..top).

% demo: classic transitive closure building blocks
edge(a, b).
edge(b, c).
edge(c, d).

reachable(X, Y) :- edge(X, Y).
reachable(X, Y) :- edge(X, Z), reachable(Z, Y).
