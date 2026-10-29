# LEARN T-007 - The Fact box
Built: One Fact record holds a number, its unit, its meaning and the exact place it came from.
It turns into text and back again without changing a digit.
Why this way: The value is a Decimal (exact decimal number) stored as text in JSON, so "0.140" keeps its zero.
We did NOT use float or JSON numbers: they can silently change 0.140 into 0.14 or 0.1400000001.
The box refuses bad data when it is created, so wrong numbers cannot get in quietly.
New words: dataclass = a short way to define a record with named fields; frozen = cannot be changed after creation; round trip = save to text and load back, result must be identical
Look at: ectd_engine/facts/schema.py - the __post_init__ methods hold all the refusal rules.
Try it: python -m unittest tests.test_fact_schema -v - you should see 22 tests, all ok.
Remember: A number without an exact source and exact digits is not a fact.
