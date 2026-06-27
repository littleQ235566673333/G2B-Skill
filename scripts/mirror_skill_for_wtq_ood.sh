#!/bin/bash
# Mirror SS-trained xlsx skill into wtq/ structure for OOD eval
# Copies xlsx/SKILL.md content to wtq/SKILL.md but swaps name field
SS_TRAIN_DIR=$1  # e.g. results/runs/g2b-skill-spreadsheet_gpt-5.4_c-topo-FIX-V-SS54-N3-seed0/train/final_skill
if [ -z "$SS_TRAIN_DIR" ] || [ ! -d "$SS_TRAIN_DIR/xlsx" ]; then
  echo "usage: $0 <SS_train_final_skill_dir>"
  exit 1
fi
TGT=$SS_TRAIN_DIR/wtq
rm -rf $TGT
cp -r $SS_TRAIN_DIR/xlsx $TGT
# Swap name field in YAML frontmatter
.venv/bin/python -c "
import re
p = '$TGT/SKILL.md'
s = open(p).read()
# Replace 'name: xlsx' (in YAML frontmatter) with 'name: wtq'
new = re.sub(r'^(\s*name:\s*)xlsx', r'\1wtq', s, count=1, flags=re.M)
open(p, 'w').write(new)
print(f'wtq mirror written: {p}')
"
