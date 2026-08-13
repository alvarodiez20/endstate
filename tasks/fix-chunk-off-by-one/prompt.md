`chunker/chunk.py` splits a list into fixed-size chunks. It drops the last
chunk whenever the list length is not an exact multiple of the chunk size,
so `chunk([1, 2, 3, 4, 5], 2)` loses `[5]`.

Fix `chunk()` so every element ends up in exactly one chunk, preserving
order. The final chunk may be shorter than `size`. Keep raising `ValueError`
for a non-positive `size`.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
