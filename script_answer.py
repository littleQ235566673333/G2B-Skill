import re
with open('results/runs/g2b-v8_gpt-4.1_wtq-gpt41/eval_seed2/eval_nt-216_tc1/oneline_input.csv') as f:
    d = f.read()
pattern = r'"([0-9]{4})",\"([^"]+)\",\"([0-9]+|—)\",\"([0-9]+|—)\",\"([^"]+)\"'
tracks = re.findall(pattern, d)
songs = [(song, int(us)) for year, song, us, can, album in tracks if us.isdigit()]
if songs:
    top_song = min(songs, key=lambda x: x[1])[0]
    with open('results/runs/g2b-v8_gpt-4.1_wtq-gpt41/eval_seed2/eval_nt-216_tc1/output.txt','w') as f:
        f.write(top_song + '\n')
else:
    with open('results/runs/g2b-v8_gpt-4.1_wtq-gpt41/eval_seed2/eval_nt-216_tc1/output.txt','w') as f:
        f.write('No song found\n')
