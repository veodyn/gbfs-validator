import json
import pathlib

from gbfs_validator.schema.formats import FORMATS

FIX = pathlib.Path(__file__).parent / "fixtures/formats"


def test_matches_ajv_formats() -> None:
    goldens = json.loads((FIX / "goldens.json").read_text())
    for fmt, cases in goldens.items():
        for sample, expected in cases.items():
            assert FORMATS[fmt](sample) is expected, (fmt, sample)


def test_goldens_cover_every_corpus_sample() -> None:
    corpus = json.loads((FIX / "corpus.json").read_text())
    goldens = json.loads((FIX / "goldens.json").read_text())
    assert set(goldens) == set(corpus) == set(FORMATS)
    for fmt, samples in corpus.items():
        assert set(samples) == set(goldens[fmt])
