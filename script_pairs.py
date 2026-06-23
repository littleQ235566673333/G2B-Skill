with open('input_words.txt') as f:
    words = [w.strip() for w in f if w.strip()]
word_map = {}
for w in words:
    # Only consider words of len>=5
    if len(w) >= 5:
        ending = w[-3:]
        if ending not in word_map:
            word_map[ending] = []
        word_map[ending].append(w)
def find_and_transform(words, word_map):
    pairs = []
    for w in words:
        if len(w) < 5:
            continue
        ending = w[-3:]
        # Only consider group if more than one with same ending
        candidates = word_map.get(ending, [])
        if len(candidates) > 1:
            if len(w) >= 5:
                new_word = w[4] + w[:4] + w[5:] if len(w) > 5 else w[4] + w[:4]
                if new_word != w and new_word in candidates:
                    pairs.append((new_word, w, ending))
    return pairs
pairs = find_and_transform(words, word_map)
prio = ['ING', 'ERS', 'ATE', 'EST', 'ONE', 'IER', 'ILY']
def sort_key(t):
    ending = t[2]
    idx = prio.index(ending) if ending in prio else 99
    return (idx, ending, t[1], t[0])
pairs.sort(key=sort_key)
with open('pairs_sorted.txt', 'w') as f:
    for t in pairs:
        f.write(f'{t[0]}\t{t[1]}\t{t[2]}\n')
print(len(pairs))
