# Small-Assistant

Small-Assistant is a Japanese-learning companion. It keeps a personal vocabulary
list and provides review, quizzes, notes, composition feedback,
conjugation and AI word checking in a web interface.

AI word checking also completes missing readings, meanings and parts of speech,
checks spelling, and requests dictionary forms for conjugated verbs and adjectives.
Readings and meanings follow the restored entry. Names, ambiguous entries and
independent attributives are preserved. Review the AI suggestions before applying
them; completion and normalization depend on the selected AI provider.

## Connection test

After signing in, open `/ping` to see your IP address and automatically measure
the browser-to-website HTTP round-trip time in milliseconds. Use **Test again**
to repeat the measurement. This includes server processing and is not ICMP ping.
The authenticated `/ping?probe=1` endpoint returns `{"ip": "...", "pong": true}`;
the browser measures the elapsed time, not the server.

The same page includes an int/float generator (default: int, 0 to 1; allowed
bounds: -9007199254740991 to 9007199254740991). The **Generate 0 to 100** button
sets the bounds to 0 and 100 and immediately generates using the selected type.
Integers include both bounds. Floats use a 53-bit fraction and exclude the upper
bound; equal bounds return that value. Float mode accepts decimal bounds.
The authenticated `POST /api/ping/random` accepts JSON
`{"minimum": 0, "maximum": 1, "number_type": "int"}` (or `"float"`) and returns
`value`, source names, and warnings for unavailable sources. Source values such
as machine codes and server IPs are not sent to the browser. Omitting
`number_type` retains the original integer behavior.

The implementation uses a handwritten FNV-1a seed mixer and SplitMix64 generator
with rejection sampling, not random-number libraries. Inputs include the client
connection IP and the **server's** nanosecond system/monotonic clocks, request
counter, machine identifier, hostname-resolved IPv4/IPv6 addresses, and OS-reported
CPU frequency. Machine identifiers and frequencies are read using macOS or Linux
interfaces; unavailable inputs are reported and omitted. macOS may expose only
a nominal CPU frequency, or none (common on Apple Silicon), not a live frequency.
These inputs are not guaranteed entropy: this is a non-cryptographic generator,
unsuitable for secrets, verification codes, or monetary draws.

## Second-round simplified Chinese

The language picker includes **二简字（1977草案）**, based on the 1977 draft of
the Second Chinese Character Simplification Scheme. Its interface catalog is
derived from the existing Simplified Chinese catalog and applies the draft's
character substitutions; meaning translations use Simplified Chinese as their
base and apply the same substitutions. This is a historical, withdrawn draft,
not a current standard. Some rare draft characters may not be supported by
every system font. This setting changes interface text only, not saved vocabulary.
The converter applies listed character substitutions only; it does not infer
component-wide simplifications or resolve context-dependent variants.

Reference: [Second Chinese Character Simplification Scheme (draft)](https://zh.wikisource.org/wiki/%E7%AC%AC%E4%BA%8C%E6%AC%A1%E6%B1%89%E5%AD%97%E7%AE%80%E5%8C%96%E6%96%B9%E6%A1%88%EF%BC%88%E8%8D%89%E6%A1%88%EF%BC%89).
