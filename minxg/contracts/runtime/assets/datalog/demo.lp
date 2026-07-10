% MINXG Datalog demo — graph algorithm + scheduling benchmark.
%
% Demostrates:
%   1. Transitive closure on a 6-node graph
%   2. Cycle detection
%   3. Degree counting
%   4. Connected component finding

#const top = 100.

% ── Demo graph ─────────────────────────────────────────────
edge(a, b).  edge_weight(a, b, 3).
edge(b, c).  edge_weight(b, c, 5).
edge(c, d).  edge_weight(c, d, 2).
edge(d, e).  edge_weight(d, e, 7).
edge(e, f).  edge_weight(e, f, 1).
edge(f, a).  edge_weight(f, a, 4).  % creates cycle
edge(a, d).  edge_weight(a, d, 6).  % shortcut

% Task scheduling demo
% task(task_id, duration, resource).
task(t1, 3, cpu).
task(t2, 2, mem).
task(t3, 4, cpu).
task(t4, 1, io).
task(t5, 2, mem).

% ── Show what we compute ───────────────────────────────────
#show tclose/2.
#show cycle/1.
#show out_degree/2.
#show in_degree/2.

% ── Answer set ─────────────────────────────────────────────
% Clingo will enumerate the reachable pairs and cycle nodes.
