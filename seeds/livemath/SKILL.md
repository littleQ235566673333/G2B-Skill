---
name: livemath
description: Use this skill whenever the user gives a math competition problem (Olympiad, AMC, Putnam, college-entrance) and expects a single final answer. The task is to reason carefully, optionally with symbolic Python (sympy), then write the final answer to output.txt — one line, the literal expression. The evaluator judges via mathematical equivalence so LaTeX vs ASCII does not matter, but missing solutions or wrong values do.
---

# Math competition problem solving

The input is `question.txt`: one problem statement, sometimes long, often
with mixed math notation (LaTeX-ish or plain text). The output goes to
`output.txt`: one line with the final answer.

The evaluator runs an LLM-judge that accepts mathematically equivalent
forms — `8√5 - 16` ≡ `8\\sqrt{5}-16` ≡ `-16 + 8 sqrt 5` ≡ `8 sqrt(5) - 16`.
But it does NOT accept partial answers when the problem asks for all
values, nor wrong-sign or wrong-magnitude.

## Quick Start

```python
from pathlib import Path
import sympy as sp

q = Path("question.txt").read_text(encoding="utf-8")

# Read carefully → set up the problem in sympy → solve.
x = sp.symbols("x", real=True)
sol = sp.solve(x**2 - 2*x - 1, x)
# sol == [1 - sqrt(2), 1 + sqrt(2)]

answer = "x = 1 + sqrt(2) or x = 1 - sqrt(2)"
Path("output.txt").write_text(answer + "\n", encoding="utf-8")
```

## Strategy that works well

1. **Extract the ask precisely.** Olympiad problems often hide the actual
   question in a long setup. Identify whether the answer is:
   - a single number / expression
   - a set of values (then enumerate all)
   - a yes/no plus a witness (then provide both)
   - a closed-form formula in n / k

2. **Try symbolic first.** sympy handles `solve`, `simplify`, `factor`,
   `Sum`, `integrate`, `Matrix`, `Polynomial`, modular arithmetic.
   Symbolic answers compose naturally with the judge's equivalence check.

3. **Fall back to numeric verification.** When you suspect a closed form,
   evaluate it numerically and cross-check with brute-force enumeration
   on a small case (n=1..5 etc.). If numeric and closed-form match to
   high precision, ship the closed form.

4. **For combinatorics / number theory**, brute-force the small cases
   first to find the pattern, then prove it (or trust pattern-fit if
   pattern holds for many cases).

## Sympy patterns that come up often

```python
# Solve algebraic equations
sp.solve(eq, x)                    # exact roots
sp.solveset(eq, x, sp.Reals)       # over reals only

# Simplification / forms
sp.simplify(expr); sp.radsimp(expr); sp.together(expr)
sp.nsimplify(expr.evalf(), [sp.sqrt(2), sp.pi])  # recognize closed forms

# Number theory
sp.isprime(n); sp.factorint(n); sp.gcd(a, b); sp.totient(n)
sp.mod_inverse(a, m)               # modular inverse

# Combinatorics
sp.binomial(n, k); sp.factorial(n)
from sympy.functions.combinatorial.numbers import bell, catalan, fibonacci

# Sums and recurrences
n = sp.symbols("n", integer=True, positive=True)
sp.summation(sp.Rational(1, sp.symbols("k")**2), (sp.symbols("k"), 1, n))
sp.rsolve(eq, f(n))                # recurrence

# Geometry
sp.Point(0, 0); sp.Line(...); sp.Circle(...)
```

## Output format

- One line, plain text.
- `\\boxed{...}` is allowed (stripped before scoring).
- Multi-value answers: a clear separator works — `x = 1 or x = 2`,
  `1, 2, 3`, `(2, 5)`, `{1, 4, 9}`.
- For "find all" problems, list ALL solutions. The judge scores zero if
  any required solution is missing.

## Common Pitfalls

- **Missing branches**: `x^2 = 4` → `x = ±2`, both required.
- **Range constraints ignored**: "for positive integers n" — re-check
  that all your sympy solutions satisfy the constraint.
- **Float bleeding into final answer**: `1.4142135` is wrong if `sqrt(2)`
  is the closed form. Use `nsimplify` to recover.
- **Question asks for the COUNT, you wrote the values**: re-read the ask
  before writing.
- **Answer in wrong units / wrong base**: degrees vs radians, decimal vs
  fraction, `\\pmod m` form.
- **Don't include working / explanation in output.txt** — only the final
  answer. The judge scores on the final answer line.
