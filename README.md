# gbfs-validator (Python)

[![CI](https://github.com/veodyn/gbfs-validator/actions/workflows/ci.yml/badge.svg)](https://github.com/veodyn/gbfs-validator/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gbfs-validator)](https://pypi.org/project/gbfs-validator/)
[![Python versions](https://img.shields.io/pypi/pyversions/gbfs-validator)](https://pypi.org/project/gbfs-validator/)
[![License](https://img.shields.io/pypi/l/gbfs-validator)](https://github.com/veodyn/gbfs-validator/blob/main/LICENSE)

Validate GBFS feeds from Python. No Node, and no dependencies.

The reference GBFS validator is [MobilityData's][upstream], written in
JavaScript. Using it from Python means Node somewhere in your stack: a base
image to maintain, a lockfile to keep current, and a subprocess and a file
handoff at the seam. Or you call their hosted lambda, whose own OpenAPI
document advises against building production systems on it.

This is the same rule set, reimplemented, for the case where you would rather
have none of that.

```bash
pip install gbfs-validator
gbfs-validator -u https://gbfs.example.com/gbfs.json
```

Python 3.11 or newer. This project shares a name with the software it
reimplements; below, "upstream" always means MobilityData's Node validator.

## What you get

One JSON report on stdout, or in a file with `-s`. The summary says what was
validated and how badly it went:

```json
{
  "validatorVersion": "0.1.0",
  "version": {"detected": "2.3", "validated": "2.3"},
  "hasErrors": true,
  "errorsCount": 1
}
```

Then one entry per file the feed's version declares, whether or not the feed
publishes it, so a missing required file is visible as a fact rather than as
an absence:

```json
{
  "file": "station_status.json",
  "required": true,
  "exists": false,
  "hasErrors": true,
  "errorsCount": 1
}
```

Files the feed does publish carry their notices, each naming the exact field.
Three real ones, with their JSON flattened to a line apiece:

```
system_information.json  /data                                      required   must have required property 'rental_apps'
vehicle_types.json       /data/vehicle_types/0/default_pricing_plan_id  enum   must be equal to one of the allowed values
free_bike_status.json    /data/bikes/0                              required   must have required property 'current_range_meters'
```

Those three come from one feed, and none of them is a plain schema check.
Each fired because of what some *other* file in the feed said: one vehicle
carries an iOS `rental_uris`, which makes `rental_apps` required over in
`system_information.json`; the published pricing plans decide which
`default_pricing_plan_id` values are legal in `vehicle_types.json`; and that
vehicle's type is `electric_assist`, which makes `current_range_meters`
required on every vehicle referencing it. Nineteen such rules patch the
schemas at run time, and they are most of what a JSON Schema alone would
miss.

For pre-3.0 feeds, which publish one copy of each file per language, entries
carry a `languages` array and each language reports separately.

The exit code is 0 whether or not notices fired, because the report is the
output. Add `--fail-on-error` to exit 1 when the feed has notices, which is
what you want in CI. A tool failure exits 1, as does asking for no output at
all; an unrecognized flag exits 2, which is argparse's convention.

## Running it

```bash
gbfs-validator -u https://gbfs.example.com/gbfs.json      # print the report
gbfs-validator -u ./feed-dir -s reports/report.json -pr no  # save it instead
```

`-u` takes an `http(s)` URL, a path to a `gbfs.json`, or a directory holding
one. The version comes from the feed; `--feed-version` overrides it.

Three files are required only for systems that have them, so the validator has
to be told which kind of system it is looking at, exactly as upstream's web
form asks:

```bash
gbfs-validator -u <url> --docked          # station_information, station_status
gbfs-validator -u <url> --free-floating   # free_bike_status / vehicle_status
```

Without either flag those files are optional and their absence is not a
notice. This is upstream's behaviour, and it is the one thing most likely to
make two runs of the same feed disagree.

## From Python

```python
from gbfs_validator import validate_feed

report = validate_feed("https://gbfs.example.com/gbfs.json", docked=True)

report["summary"]["hasErrors"]  # True
report["summary"]["errorsCount"]  # 1
```

`GBFS(url, docked=..., freefloating=..., version=..., auth=...)` gives the
same report from `.validation()`. Both are synchronous and return plain dicts.

Authenticated feeds work through the Python API, in all four of upstream's
modes:

```python
from gbfs_validator import GBFS

GBFS(url, auth={"type": "bearer_token", "bearerToken": {"token": "..."}}).validation()
GBFS(url, auth={"type": "headers", "headers": [{"key": "X-Api-Key", "value": "..."}]}).validation()
```

The others are `basic_auth` and `oauth_client_credentials_grant`, shaped as
upstream shapes them. There are no CLI flags for these yet, deliberately:
there is no fixture for a real authenticated feed to test them against.

## Which versions

v1.0, v1.1, v2.0, v2.1, v2.2, v2.3, v3.0 and v3.1-RC3, from 96 JSON Schemas
vendored out of MobilityData's [`gbfs-json-schema`][schemas] at a pinned
commit. That is upstream's range too, including the 3.1 release candidate,
which `--feed-version 3.1-RC3` selects.

The version normally comes from `gbfs.json` and is detected per feed. The
override exists because a feed can declare one version and be shaped like
another.

## How close is it?

Close enough that swapping the binary is meant to be the entire change, and
that is tested rather than asserted. Three harnesses cover different ground.

**32 feeds through both validators.** `tools/differential.py` serves each
fixture feed over HTTP, runs this validator and the pinned upstream against
it, and fails on any difference in which notices fired, on which file, at
which path, with which parameters. The corpus covers all eight versions, both
system kinds, every conditional rule, multi-language feeds with a language
missing, both ways a manifest can appear, and feeds malformed enough that the
interesting question is whether both validators crash in the same place.

**90 schema cases and 34 format samples, generated by upstream's own AJV
stack.** The engine here is a draft-07 subset written from scratch, so its
oracle is `upstream/gbfs-validator/validate.js` itself: cases go through it,
the errors it returns are committed, and the suite compares. The 19 conditional
rules are compared the same way, against the JavaScript generators that build
them. When a golden and this engine disagree, the engine is what changes.

**32 real systems, sampled from MobilityData's catalog.** Fixtures only cover
what someone thought to write down. `tools/real_feed_sweep.py` samples live
systems and compares both validators on them; the last sweeps agreed on every
feed sampled, including ones carrying 4,149 and 5,390 notices.

Live feeds carry a trap worth naming. Vehicle positions change between two
sequential fetches, so comparing one validator's view against the other's
invents differences that were never there. Every feed is snapshotted before
comparison for that reason, and the one divergence a sweep did report turned
out to be exactly this: 740 against 754 live, 762 against 762 once frozen.

## Deliberate differences

Everything here was measured against the pinned upstream and kept on purpose.
Anything *not* on this list is a bug worth reporting.

**A failed run exits non-zero.** Upstream returns 0 from its critical-error
path in every case; here a tool failure exits 1, so a broken run is visible to
a pipeline. Feeds with notices still exit 0 unless you pass `--fail-on-error`,
so swapping the binary cannot silently change what your pipeline does.

**The report is JSON.** Upstream's stdout is Node's `util.inspect` rendering,
which is meant for reading rather than parsing.

**Local feeds are accepted.** Upstream takes a URL; this also takes a
directory or a `gbfs.json` path, which is what you want in a test suite.

**Options upstream only exposes through its JS API.** `--docked`,
`--free-floating` and `--feed-version` are reachable from the CLI here;
upstream's CLI constructs `new GBFS(url)` and offers none of them.

**CLI output drops `body` and `schema`.** Upstream echoes every fetched file
body and every compiled schema back into the report, which makes it enormous
and mostly a copy of the feed you already have. `--include-schema` restores
the schema. This is a CLI concern only: the Python API returns the full
report.

**Files are fetched one at a time**, not with `Promise.all`. All files are
still collected before any cross-file rule runs, so reports are unaffected.

**HTTP is urllib's**: no retries, a 30 second timeout, no compression
negotiation. Any failure, network or status or decode, becomes `exists: false`
for that file, which is what upstream's `catch` does.

**Message strings are mimicked, not guaranteed.** AJV's wording is reproduced
where it is cheap, but the differential compares which notices fire and where,
not their prose.

## Edges worth knowing about

Some of what a report does is surprising enough to look like a defect here.
These are the cases worth knowing before you go looking for one. Each matches
upstream, and each has a test pinning it there, so a well-meant cleanup fails
the suite rather than quietly ending parity.

**An `errorsCount` can be `null`.** When per-language counts are summed, a
language that validated cleanly contributes `false` rather than a list, and
reading a length from it yields `NaN`, which JSON renders as `null`. One such
file makes the summary total `null` too. Any multi-language feed with one
clean language and one that has notices lands here.

**JavaScript truthiness decides the conditional rules.** They read feed data
before it has been validated, so `""` and `0` are falsy while `[]` and `{}`
are truthy. A vehicle whose `vehicle_type_id` is an empty string does not make
`vehicle_types.json` required; one whose `vehicle_type_id` is an empty array
does.

**A badly malformed feed ends the run instead of producing a notice.** Those
same rules reach into `data.vehicle_types` and `data.bikes` before those files
are validated, so a feed publishing an object where the spec wants an array
stops the run. Reporting it as a notice would be friendlier, and would not
match.

**A pre-v3 feed carrying a `manifest_url` also ends the run**, because the
manifest is fetched for every version but only has a schema from 3.0 onward.

**A missing OAuth `access_token` yields the literal header `Bearer
undefined`** and the run continues, rather than stopping there.

**The autodiscovery fallback matches loosely.** The check for a URL that
already points at the discovery document is the pattern `/gbfs.json$/`, whose
dot is unescaped and so matches any character. A feed served at `/gbfs_json`
counts as already being that document.

## Working on it

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
python -m pytest -q
ruff check . && ruff format --check . && pyright
```

336 tests, no Node required: the oracles are committed, so the suite checks
against what upstream said rather than needing upstream present. Branch
coverage is 93%.

To run the parity harnesses you need the pinned clone and Node, at least 18
because that is what upstream's `engines` field requires. CI uses 20, and the
committed goldens were generated on 24:

```bash
bash tools/sync_upstream.sh     # clone at the pin, frozen lockfile
python tools/sync_schemas.py    # vendor the JSON Schemas
python tools/differential.py    # 32 fixture feeds, both validators
python tools/real_feed_sweep.py # live systems from the catalog
```

`tools/differential.py --write-expectations` records upstream's verdict for
every fixture feed into `tests/fixtures/feeds/expectations.json`, which is what
the Node-free suite compares against. Regenerate it in the same commit as any
fixture change, and read the diff: a changed expectation means upstream's
behaviour changed, and that deserves its own commit.

Goldens are generated, never hand-edited. Each generator under `tools/node/`
rewrites `tests/fixtures/META.json` alongside its output, recording the Node
version, both pins and the lockfile hash the goldens were produced with.

What none of this covers is input nobody thought to build. Every parity defect
found late was on a feed shape no fixture carried, which is why the real-feed
sweep exists and why a green run means "matches on the feeds we have".

## Relationship to upstream

An independent reimplementation, not an official port, not affiliated with
MobilityData and not endorsed by them. The JSON Schemas are vendored from
their Apache-2.0 project and the conditional rules are ported from it;
[`NOTICE`](https://github.com/veodyn/gbfs-validator/blob/main/NOTICE) names what is copied rather than derived. The shared name
describes what the software does; it is not a claim of origin.

| What | Pin |
|---|---|
| `MobilityData/gbfs-validator` | `b734086` |
| `MobilityData/gbfs-json-schema` | `916327f` |

Both are pinned by commit because neither publishes releases that parity could
be stated against. `src/gbfs_validator/data/PIN` carries the same two SHAs
inside the installed package, so a report can be traced to the schemas that
produced it.

Where upstream and this project's intuition disagree, upstream wins. A check
that looks wrong is almost always faithful, and a red differential is the
deliverable rather than an obstacle.

## License

MIT; see [`LICENSE`](https://github.com/veodyn/gbfs-validator/blob/main/LICENSE).

The vendored schemas stay under upstream's Apache-2.0 licence.
[`NOTICE`](https://github.com/veodyn/gbfs-validator/blob/main/NOTICE) names each file and explains the shared name.

[upstream]: https://github.com/MobilityData/gbfs-validator
[schemas]: https://github.com/MobilityData/gbfs-json-schema
