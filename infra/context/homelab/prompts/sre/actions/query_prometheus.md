
Interpret the Prometheus result for the alert window. Distinguish current, recurring, and historical
symptoms. Use metric evidence to confirm the root cause or recovery; do not infer a fix from one noisy sample.
When a query returns an error, read the reason and correct the query before relying on that metric: for example,
add `group_left` or `group_right` when Prometheus reports many-to-one matching, fix syntax it reports, or narrow
the selector or range. Do not repeat a rejected query unchanged.
