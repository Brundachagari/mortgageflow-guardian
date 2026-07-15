# Sample documents

**All files here are FICTIONAL / SYNTHETIC.** No real person, employer, or
financial data is used.

`fictional_pay_stub.json` is used by the local demo (`python demo.py`).

The other files are for the **AWS demo**: upload one to `s3://<bucket>/incoming/`
and the mock processor picks a scenario from the file name, so you can trigger
every path on purpose:

| File | Path it exercises |
|---|---|
| `paystub_clean.json` | PROCESSED |
| `paystub_lowconf.json` | NEEDS_REVIEW (low confidence) |
| `paystub_missing.json` | NEEDS_REVIEW (missing field) |
| `paystub_timeout.json` | transient error → retries → dead-letter |
| `paystub_corrupt.json` | permanent failure → dead-letter |
