% MINXG Datalog bridge — industrial-grade logic/reasoning engine.
%
% This bridge provides reusable predicates for:
%   - Graph algorithms (path finding, reachability, transitive closure)
%   - Type inference / constraint solving
%   - Scheduling / resource allocation
%   - Set operations (intersection, union, membership)
%
% It ships as a real .lp file that clingo reads, not a Python string.
% User code is appended below this bridge header.

% ── Core graph theory ──────────────────────────────────────

% Transitive closure of any edge/1 relation
tclose(X, Y) :- edge(X, Y).
tclose(X, Y) :- edge(X, Z), tclose(Z, Y).

% Path with length tracking (up to max_len)
% path(From, To, Len)
path(X, Y, 1) :- edge(X, Y).
path(X, Y, Len) :- edge(X, Z), path(Z, Y, L1), Len = L1 + 1, Len <= top.

% Cycle detection
cycle(X) :- edge(X, Y), tclose(Y, X).

% Connected components via least element
component(X, X) :- node(X), not dominated(X).
component(X, R) :- edge(X, Y), component(Y, R), X != R.
dominated(X) :- edge(X, Y), Y < X, tclose(Y, X).

% ── Set operations ─────────────────────────────────────────

% Set membership (explicit elements)
in_set(Element, Set) :- set_element(Set, Element).

% Set intersection
in_intersection(E, A, B) :- in_set(E, A), in_set(E, B).

% Set union
in_union(E, A, B) :- in_set(E, A).
in_union(E, A, B) :- in_set(E, B).

% Subset check: A ⊆ B
is_subset(A, B) :- set(A), set(B), A != B,
    #count { E : in_set(E, A), not in_set(E, B) } = 0.

% ── Scheduling constraints ────────────────────────────────

% Basic resource-constrained scheduling
% task(T, Duration, Resource).  resource(R, Capacity).
% assign(T, Slot) means task T starts at Slot.
schedule(T, Slot) :- task(T, Dur, _Res), Slot = 1..top-Dur+1,
    not conflict(T, Slot).
conflict(T1, S1) :- task(T1, D1, R), task(T2, D2, R), T1 != T2,
    schedule(T2, S2), S2 >= S1, S2 < S1 + D1,
    R = R.

% ── Type inference ─────────────────────────────────────────

% Simple Hindley-Milner style type inference
typeof(X, T) :- literal_type(X, T).
typeof(X, T) :- assign(X, E), typeof(E, T).

% Function composition: if f:A->B and g:B->C, then g∘f:A->C
compose(F, G, A, C) :- fun_type(F, A, B), fun_type(G, B, C).

% ── Node/Edge helpers ──────────────────────────────────────

% Derive node set from edges
node(X) :- edge(X, _).
node(X) :- edge(_, X).

% Degree counting
out_degree(X, D) :- node(X), D = #count { Y : edge(X, Y) }.
in_degree(X, D)  :- node(X), D = #count { Y : edge(Y, X) }.

% ── Reachability with constraints ──────────────────────────

% Reachable only through positive-weight edges
reachable_pos(X, Y) :- edge(X, Y), edge_weight(X, Y, W), W > 0.
reachable_pos(X, Y) :- edge(X, Z), reachable_pos(Z, Y),
    edge_weight(X, Z, W), W > 0.

% ── Show directives ───────────────────────────────────────
#show tclose/2.
#show path/3.
#show cycle/1.
#show component/2.
#show in_intersection/3.
#show in_union/3.
#show is_subset/2.
#show out_degree/2.
#show in_degree/2.
#show reachable_pos/2.
