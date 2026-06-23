=== v8 + anti-wipe trace pre-check (WTQ GPT-4.1) ===
run_id: g2b-v8_gpt-4.1_wtq-gpt41-fix

Patch counts:
  accepted patches:  10
  proposed patches available: 10

Layer A — accepted patch stats (S_old → S_new_accepted):
  high_ratio_patch_rate (any section >0.5): 10%
  deleted_section_patch_rate:              20%
  added_section_patch_rate:                60%
  mean of max_section_edit_ratio:          0.185
  mean of mean_section_edit_ratio:         0.037
  max observed section edit ratio:         0.577

Layer B — proposed patch stats (S_old → S_new_proposed):
  high_ratio_patch_rate (any section >0.5): 20%
  deleted_section_patch_rate:              60%
  added_section_patch_rate:                80%
  mean of max_section_edit_ratio:          0.306
  mean of mean_section_edit_ratio:         0.159
  max observed section edit ratio:         0.944

Go/No-go decision:
  GO if (high_ratio_rate ≥ 20%) OR (deleted_rate ≥ 10%)
  Decision: GO
  Rationale: deleted_rate 20% ≥ 10%

Per-iter Layer A details:
  iter | n_old n_new | matched del add | max_ratio mean_ratio
     1 |     3     6 |       3   0   3 |     0.277      0.166
     2 |     6     6 |       6   0   0 |     0.000      0.000
     3 |     6     9 |       6   0   3 |     0.141      0.024
     4 |     9    12 |       9   0   3 |     0.325      0.051
     5 |    12    12 |      12   0   0 |     0.000      0.000
     6 |    12    12 |      12   0   0 |     0.000      0.000
     7 |    12    15 |      12   0   3 |     0.160      0.013
     8 |    15    15 |      14   1   1 |     0.577      0.071  *high
     9 |    15    15 |      15   0   0 |     0.000      0.000
    10 |    15    16 |      14   1   2 |     0.366      0.048

Per-iter Layer B details (proposed before anti-wipe revert):
  iter |  prop B   acc B  reverted | max_ratio
     1 |    4997    4997           |     0.277
     2 |    2167    4997       YES |     0.944  *high
     3 |    7413    7413           |     0.141
     4 |   10041   10041           |     0.325
     5 |    2929   10041       YES |     0.000
     6 |    1264   10041       YES |     0.268
     7 |   12651   12651           |     0.160
     8 |   14579   14579           |     0.577  *high
     9 |    3428   14579       YES |     0.000
    10 |   16386   16386           |     0.366