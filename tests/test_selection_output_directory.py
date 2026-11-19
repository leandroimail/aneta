from src.Selection import create_folder


def test_preserve_existing_review_outputs(tmp_path):
    review = tmp_path / "my.bibs.review"
    inputs = review / ".bibs"
    inputs.mkdir(parents=True)
    create_folder(str(inputs))
    prior = review / "OUTPUTS" / "prior-decision.json"
    prior.write_text("preserve")
    create_folder(str(inputs))
    assert prior.read_text() == "preserve"
