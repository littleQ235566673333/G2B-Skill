import pandas as pd

def main():
    in_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/eval_seed42/eval_nt-64_tc1/input.csv'
    out_path = 'results/runs/g2b-skill-wtq_gpt-4.1_c-topo-wtq41-seed0/eval_seed42/eval_nt-64_tc1/output.txt'
    
    df = pd.read_csv(in_path)
    # Lowercased dataframe for universal matching
    df_lower = df.applymap(lambda x: str(x).lower() if isinstance(x, str) else str(x))
    # Find rows mentioning 'virginia'
    virginia_rows = df_lower.apply(lambda row: row.astype(str).str.contains('virginia').any(), axis=1)
    df_virginia = df[virginia_rows]
    # Find the district column
    district_cols = [col for col in df.columns if 'district' in col.lower()]
    if district_cols:
        count = df_virginia[district_cols[0]].nunique()
    else:
        count = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"{count}\n")

if __name__ == "__main__":
    main()
