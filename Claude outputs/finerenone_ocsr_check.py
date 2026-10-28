"""
Finerenone structure-recognition check (MolScribe + RDKit).

Usage:
    python finerenone_ocsr_check.py finerenone.png

Needs: pip install molscribe rdkit huggingface_hub torch
The script downloads the MolScribe weights from Hugging Face (yujieq/MolScribe).
"""
import sys

import torch
from huggingface_hub import hf_hub_download
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors
from molscribe import MolScribe

# Label values (FDA label, NDA 215341): C21H22N4O3, 378.43 g/mol.
LABEL_FORMULA = "C21H22N4O3"
LABEL_MW = 378.43

# Reference structure built from the chemical name (no stereo).
# Only formula and weight have been checked against the label so far.
REFERENCE_SMILES = "CCOc1ncc(C)c2c1C(c1ccc(C#N)cc1OC)C(C(N)=O)=C(C)N2"


def connectivity_key(mol):
    """InChIKey first block: the connectivity layer, ignores stereo."""
    return Chem.MolToInchiKey(mol).split("-")[0]


def main(image_path):
    ckpt = hf_hub_download("yujieq/MolScribe", "swin_base_char_aux_1m.pth")
    model = MolScribe(ckpt, device=torch.device("cpu"))

    result = model.predict_image_file(image_path, return_confidence=True)
    smiles = result.get("smiles", "")
    print("OCSR SMILES:", smiles)
    print("OCSR confidence:", result.get("confidence"))

    mol = Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:
        print("RESULT: FAIL - SMILES did not parse")
        return

    formula = rdMolDescriptors.CalcMolFormula(mol)
    mw = round(Descriptors.MolWt(mol), 2)
    print("Formula:", formula, "(label:", LABEL_FORMULA + ")")
    print("MW:", mw, "(label:", LABEL_MW, ")")

    ref = Chem.MolFromSmiles(REFERENCE_SMILES)
    same_connectivity = connectivity_key(mol) == connectivity_key(ref)
    print("Same connectivity as reference:", same_connectivity)

    ok = formula == LABEL_FORMULA and abs(mw - LABEL_MW) < 0.01
    print("RESULT:", "PASS" if ok else "FAIL",
          "- formula and weight vs label")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
