# LEARN T-017 - Kerendia facts accepted + typing a number twice
Built: Six new unit and range rules, so all 8 Kerendia facts now pass the gate.
A tool that asks a person to type a number twice, blind, and keeps it only if both match.
Why this way: Typed numbers get the same double check as the range files. The second prompt hides what you type (getpass),
so you cannot copy the first answer. We did NOT compare as text, because "1.0" and "1" are the same number.
New words: blind entry = typing without seeing your earlier answer; refused = no fact is made at all
Look at: ectd_engine/loaders/double_entry.py - enter_twice compares Decimals, and any doubt raises Refused.
Try it: python -m ectd_engine.loaders.double_entry max_daily_dose - type 20 twice; typing 20 then 2 prints REFUSED.
Remember: A number a person typed is only trusted after two blind typings agree.
