=== v8 + anti-wipe trace pre-check (SS GPT-4.1) ===
run_id: g2b-v8_gpt-4.1_ss-gpt41-fix

Patch counts:
  accepted patches:  10
  proposed patches available: 10

Layer A — accepted patch stats (S_old → S_new_accepted):
  high_ratio_patch_rate (any section >0.5): 10%
  deleted_section_patch_rate:              10%
  added_section_patch_rate:                60%
  mean of max_section_edit_ratio:          0.184
  mean of mean_section_edit_ratio:         0.025
  max observed section edit ratio:         0.648

Layer B — proposed patch stats (S_old → S_new_proposed):
  high_ratio_patch_rate (any section >0.5): 30%
  deleted_section_patch_rate:              50%
  added_section_patch_rate:                70%
  mean of max_section_edit_ratio:          0.345
  mean of mean_section_edit_ratio:         0.145
  max observed section edit ratio:         0.969

Go/No-go decision:
  GO if (high_ratio_rate ≥ 20%) OR (deleted_rate ≥ 10%)
  Decision: GO
  Rationale: deleted_rate 10% ≥ 10%

Per-iter Layer A details:
  iter | n_old n_new | matched del add | max_ratio mean_ratio
     1 |     3     7 |       3   0   4 |     0.305      0.102
     2 |     7     9 |       6   1   3 |     0.329      0.057
     3 |     9     9 |       9   0   0 |     0.000      0.000
     4 |     9    13 |       9   0   4 |     0.028      0.003
     5 |    13    15 |      13   0   2 |     0.271      0.031
     6 |    15    18 |      15   0   3 |     0.256      0.017
     7 |    18    21 |      18   0   3 |     0.648      0.036  *high
     8 |    21    21 |      21   0   0 |     0.000      0.000
     9 |    21    21 |      21   0   0 |     0.000      0.000
    10 |    21    21 |      21   0   0 |     0.000      0.000

Per-iter Layer B details (proposed before anti-wipe revert):
  iter |  prop B   acc B  reverted | max_ratio
     1 |    3328    3328           |     0.305
     2 |    7187    7187           |     0.329
     3 |     722    7187       YES |     0.000
     4 |   10476   10476           |     0.028
     5 |   12211   12211           |     0.271
     6 |   14741   14741           |     0.256
     7 |   18571   18571           |     0.648  *high
     8 |    1724   18571       YES |     0.082
     9 |    1528   18571       YES |     0.563  *high
    10 |    5754   18571       YES |     0.969  *high