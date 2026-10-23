Work in this order and stop once the answer is supported:

1. Search for the issuer's latest dividend announcement: the company name with "dividend" and the current and
   next year, then the same in the issuer's language (for example dividende, Dividende, dividendo,
   dividendi, détachement, Ex-Tag). Add "ex-dividend date", "record date", or "annual
   general meeting" when the first results are not specific.
2. Read the most specific official release with fetch_page: the dividend press release, the AGM resolutions or
   minutes, or the investor relations dividend page. Prefer the issuer's own page or a regulatory news wire.
3. Pick the next payment: when the dividend is paid in instalments or as interim and final payments, report the
   first one whose ex-date, record date, or payment date is on or after the given date, with that instalment's
   own amount, not the annual total.
4. Report each date as the source states it. Do not derive the ex-date from the record date yourself; the
   validator applies the exchange's settlement rule. When the source states only the amount and the payment
   date, report those and leave the ex-date null.
5. Use the gross amount per share in the currency the source states. For a scrip or optional stock dividend,
   report the cash amount only when the source states one.

Each evidence quote must be one sentence or table row that contains the reported value. A date quote must
contain the date itself, not only a reference such as "the third business day after the meeting". Cite the URL
you passed to fetch_page, not the search result that led to it.
